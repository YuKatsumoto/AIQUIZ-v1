import os
import random
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional

from game.core.constants import MODE_ENDLESS, MODE_TEN
from game.core.providers.logging_hooks import (
    append_generation_reject_log,
    append_generation_source_log,
    is_bad_rated_question,
)
from game.core.providers.online_fetch import fetch_quiz_from_online_llms_parallel
from game.core.quiz_provider import OfflineQuizProvider, QuizItem
from game.core.ratings.ratings_service import RatingsService
from game.core.validation.grade_fit import grade_fit_reject_reason, is_similar_question, push_recent_question


class BufferedQuizProvider:
    def __init__(
        self,
        offline_provider: OfflineQuizProvider,
        ratings_path: str,
        reject_log_path: str,
        source_log_path: str,
        num_workers: int = 2,
        ratings_service: Optional[RatingsService] = None,
    ):
        self.offline_provider = offline_provider
        self.num_workers = max(1, num_workers)
        self.ratings_path = Path(ratings_path)
        self.reject_log_path = Path(reject_log_path)
        self.source_log_path = Path(source_log_path)
        self.ratings_service = ratings_service or RatingsService(str(self.ratings_path))

        self.buffer: Deque[QuizItem] = deque()
        self.buffer_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.workers: list[threading.Thread] = []
        self.recent_questions: Deque[str] = deque(maxlen=80)

        self.subject = "算数"
        self.grade = 3
        self.difficulty = "普通"
        self.mode = MODE_TEN
        self.target_count = 10
        self.inflight = 0
        self.llm_mode = "OFFLINE"
        self._last_online_attempt = 0.0
        self._ratings = self.ratings_service.load()
        self._adaptive_relax = 0.0
        self._recent_results: Deque[bool] = deque(maxlen=12)
        self.play_history: Deque[str] = deque(maxlen=90)
        self.preload_started_at = time.time()
        self.force_offline_fill_after_seconds = float(os.getenv("FORCE_OFFLINE_FILL_AFTER_SECONDS", "4.0"))
        self.online_fail_streak = 0
        self.online_backoff_until = 0.0

        self._start_workers()

    def _start_workers(self) -> None:
        for i in range(self.num_workers):
            t = threading.Thread(target=self._api_worker, args=(i + 1,), daemon=True)
            self.workers.append(t)
            t.start()

    def stop(self) -> None:
        self.stop_event.set()
        for t in self.workers:
            try:
                t.join(timeout=0.2)
            except Exception:
                pass

    def set_llm_mode(self, llm_mode: str) -> None:
        self.llm_mode = "ONLINE" if str(llm_mode).upper() == "ONLINE" else "OFFLINE"

    def begin_round(self, subject: str, grade: int, difficulty: str, mode: str, target_count: int) -> None:
        self.subject = subject
        self.grade = int(grade)
        self.difficulty = difficulty
        self.mode = mode
        self.target_count = int(target_count)
        self.preload_started_at = time.time()
        self.online_fail_streak = 0
        self.online_backoff_until = 0.0
        self._adaptive_relax = 0.0
        self.recent_questions.clear()
        self.play_history.clear()
        with self.buffer_lock:
            self.buffer.clear()
            self.inflight = 0

    def submit_result(self, quiz: Optional[QuizItem], correct: bool) -> None:
        self._recent_results.append(bool(correct))
        if len(self._recent_results) >= 6:
            ratio = sum(1 for x in self._recent_results if x) / len(self._recent_results)
            if ratio < 0.35:
                self._adaptive_relax = min(0.18, self._adaptive_relax + 0.03)
            elif ratio > 0.75:
                self._adaptive_relax = max(0.0, self._adaptive_relax - 0.02)
        if quiz and quiz.q:
            self.play_history.append(quiz.q)

    def mark_quiz_good(self, quiz: Optional[QuizItem], subject: str, grade: int, difficulty: str = "") -> None:
        if not quiz:
            return
        self.ratings_service.mark_good({"q": quiz.q}, subject=subject, grade=grade, difficulty=difficulty)
        self._ratings = self.ratings_service.load()

    def mark_quiz_bad(self, quiz: Optional[QuizItem], subject: str, grade: int, difficulty: str = "") -> None:
        if not quiz:
            return
        self.ratings_service.mark_bad({"q": quiz.q}, subject=subject, grade=grade, difficulty=difficulty)
        self._ratings = self.ratings_service.load()

    def _target_buffer_size(self) -> int:
        return 10 if self.mode == MODE_TEN else 4

    def _worker_should_fill(self) -> bool:
        with self.buffer_lock:
            pending = len(self.buffer) + self.inflight
        return pending < self._target_buffer_size()

    def _mark_inflight(self, delta: int) -> None:
        with self.buffer_lock:
            self.inflight = max(0, self.inflight + delta)

    def _push_quiz(self, quiz: QuizItem) -> None:
        with self.buffer_lock:
            self.buffer.append(quiz)

    def _pull_many(self, count: int) -> List[QuizItem]:
        out: List[QuizItem] = []
        with self.buffer_lock:
            while self.buffer and len(out) < count:
                out.append(self.buffer.popleft())
        return out

    def _fetch_online(self, count: int) -> List[QuizItem]:
        now = time.time()
        if now < self.online_backoff_until:
            return []
        if now - self._last_online_attempt < 0.25:
            return []
        self._last_online_attempt = now
        include_image = os.getenv("GEMINI_IMAGE_MODEL", "").strip() != ""
        results = fetch_quiz_from_online_llms_parallel(
            self.subject,
            self.grade,
            self.difficulty,
            count=count,
            include_image=include_image,
            history=list(self.play_history),
            good_examples=list(self._ratings.get("good", [])),
            bad_examples=list(self._ratings.get("bad", [])),
        )
        if results:
            self.online_fail_streak = 0
            self.online_backoff_until = 0.0
        else:
            self.online_fail_streak = min(8, self.online_fail_streak + 1)
            self.online_backoff_until = now + min(4.0, 0.5 * (2 ** max(0, self.online_fail_streak - 1)))
        return results

    def _fetch_offline(self, count: int) -> List[QuizItem]:
        out = self.offline_provider.get_quizzes(
            self.subject,
            self.grade,
            self.difficulty,
            self.mode,
            count=max(1, count),
        )
        return out

    def _validate_quiz(self, quiz: QuizItem) -> str:
        if is_bad_rated_question(self._ratings, quiz, self.subject, self.grade):
            return "bad_rated_question"
        reason = grade_fit_reject_reason(
            quiz,
            self.subject,
            self.grade,
            difficulty=self.difficulty,
            threshold_relax=self._adaptive_relax,
        )
        if reason:
            return reason
        # In TEN mode, strict similarity filtering can deadlock at N-1 questions
        # when offline bank templates are highly repetitive. Allow the final slot.
        if self.mode == MODE_TEN and len(self.recent_questions) >= max(0, self.target_count - 1):
            return ""
        if is_similar_question(quiz, self.recent_questions):
            return "similar_question"
        return ""

    def _should_force_offline_fill(self) -> bool:
        if self.llm_mode != "ONLINE":
            return False
        if self.force_offline_fill_after_seconds <= 0:
            return False
        elapsed = time.time() - self.preload_started_at
        if elapsed < self.force_offline_fill_after_seconds:
            return False
        with self.buffer_lock:
            pending = len(self.buffer) + self.inflight
        if self.mode == MODE_TEN:
            return pending < max(2, min(4, self.target_count))
        return pending < 1

    def _api_worker(self, _worker_id: int) -> None:
        while not self.stop_event.is_set():
            if self.llm_mode != "ONLINE":
                time.sleep(0.05)
                continue
            if not self._worker_should_fill():
                time.sleep(0.03)
                continue
            self._mark_inflight(+1)
            fetched: List[QuizItem] = []
            try:
                force_offline = self._should_force_offline_fill()
                if self.llm_mode == "ONLINE" and not force_offline:
                    fetched = self._fetch_online(2)
                if not fetched:
                    # TEN mode needs a wider offline candidate set; otherwise
                    # repeated small batches can be exhausted by similarity checks.
                    offline_batch = 2
                    if self.mode == MODE_TEN:
                        offline_batch = max(6, min(10, self.target_count))
                    fetched = self._fetch_offline(offline_batch)
                random.shuffle(fetched)
                for quiz in fetched:
                    reason = self._validate_quiz(quiz)
                    if reason:
                        append_generation_reject_log(
                            self.reject_log_path, quiz, self.subject, self.grade, self.difficulty, reason
                        )
                        continue
                    append_generation_source_log(
                        self.source_log_path, quiz, self.subject, self.grade, self.difficulty
                    )
                    push_recent_question(self.recent_questions, quiz)
                    self._push_quiz(quiz)
            finally:
                self._mark_inflight(-1)
            time.sleep(0.01)

    def get_quizzes(
        self,
        subject: str,
        grade: int,
        difficulty: str,
        mode: str,
        count: int,
    ) -> List[QuizItem]:
        # Keep context synced for direct pull calls.
        self.subject = subject
        self.grade = int(grade)
        self.difficulty = difficulty
        self.mode = mode
        # OFFLINE: read directly from offline_bank.json via OfflineQuizProvider
        # (buffer is only used for ONLINE / hybrid generation).
        if self.llm_mode != "ONLINE":
            return self._fetch_offline(max(1, count))
        out = self._pull_many(max(1, count))
        return out

    def is_ready_for_mode(self) -> bool:
        if self.llm_mode != "ONLINE":
            return True
        if self.mode == MODE_TEN:
            with self.buffer_lock:
                return len(self.buffer) >= min(10, self.target_count)
        with self.buffer_lock:
            return len(self.buffer) >= 1

    def buffered_count(self) -> int:
        with self.buffer_lock:
            return len(self.buffer)
