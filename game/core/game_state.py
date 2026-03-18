from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from .constants import (
    DIFFICULTY_EN,
    DIFFICULTY_LEVELS,
    MENU_STEP_CONFIG,
    MENU_STEP_MODE,
    MODE_ENDLESS,
    MODE_TEN,
    STATE_CLEAR,
    STATE_CORRECT,
    STATE_GAME_OVER,
    STATE_MENU,
    STATE_PRELOADING,
    STATE_PLAYING,
    SUBJECT_EN,
    SUBJECTS,
)
from .quiz_provider import QuizItem, QuizProvider


@dataclass
class GameTuning:
    player_speed: float = 7.6
    min_x: float = -4.9
    max_x: float = 4.9
    wall_start_z: float = 22.0
    wall_speed: float = 6.8
    door_half_width: float = 1.35
    left_door_x: float = -2.35
    right_door_x: float = 2.35
    hit_z: float = -6.0
    correct_hold_sec: float = 1.05


@dataclass
class QuizGameState:
    provider: QuizProvider
    use_english_ui: bool = False
    tuning: GameTuning = field(default_factory=GameTuning)

    subject: str = "算数"
    grade: int = 3
    difficulty: str = "普通"
    mode: str = MODE_TEN
    llm_mode: str = "OFFLINE"
    menu_step: str = MENU_STEP_MODE

    score: int = 0
    current_index: int = 0
    quiz_list: List[QuizItem] = field(default_factory=list)
    current_quiz: Optional[QuizItem] = None

    game_state: str = STATE_MENU
    choice_locked: bool = False
    message_timer: float = 0.0

    player_x: float = 0.0
    wall_z: float = 22.0

    message_text: str = ""
    status_text: str = ""

    correct_flash: float = 0.0
    wrong_flash: float = 0.0
    camera_shake: float = 0.0
    preload_wait_sec: float = 0.0
    min_preload_sec: float = 0.35
    target_count: int = 10
    recent_results: Deque[bool] = field(default_factory=lambda: deque(maxlen=12))
    rating_target_quiz: Optional[QuizItem] = None
    rating_feedback: str = ""

    def __post_init__(self):
        self.wall_z = self.tuning.wall_start_z
        self.refresh_status_text()

    def menu_input(self, key: str) -> bool:
        if key in ("enter", "space"):
            self.start_game()
            return True

        if key == "q":
            idx = SUBJECTS.index(self.subject)
            self.subject = SUBJECTS[(idx - 1) % len(SUBJECTS)]
        elif key == "e":
            idx = SUBJECTS.index(self.subject)
            self.subject = SUBJECTS[(idx + 1) % len(SUBJECTS)]
        elif key == "z":
            self.grade = max(1, self.grade - 1)
        elif key == "c":
            self.grade = min(6, self.grade + 1)
        elif key == "a":
            idx = DIFFICULTY_LEVELS.index(self.difficulty)
            self.difficulty = DIFFICULTY_LEVELS[(idx - 1) % len(DIFFICULTY_LEVELS)]
        elif key == "d":
            idx = DIFFICULTY_LEVELS.index(self.difficulty)
            self.difficulty = DIFFICULTY_LEVELS[(idx + 1) % len(DIFFICULTY_LEVELS)]
        elif key == "1":
            self.mode = MODE_TEN
        elif key == "2":
            self.mode = MODE_ENDLESS
        self.refresh_status_text()
        return False

    def start_game(self):
        self.score = 0
        self.current_index = 0
        count = 10 if self.mode == MODE_TEN else 1
        self.target_count = count
        if hasattr(self.provider, "set_llm_mode"):
            self.provider.set_llm_mode(self.llm_mode)
        if hasattr(self.provider, "begin_round"):
            self.provider.begin_round(
                subject=self.subject,
                grade=self.grade,
                difficulty=self.difficulty,
                mode=self.mode,
                target_count=count,
            )
        self.quiz_list = self.provider.get_quizzes(
            subject=self.subject,
            grade=self.grade,
            difficulty=self.difficulty,
            mode=self.mode,
            count=count,
        )
        self.message_text = ""
        self.game_state = STATE_PRELOADING
        self.preload_wait_sec = 0.0
        self.refresh_status_text()

    def select_mode_and_continue(self, mode: str):
        if mode in (MODE_TEN, MODE_ENDLESS):
            self.mode = mode
        self.menu_step = MENU_STEP_CONFIG
        self.refresh_status_text()

    def back_to_mode_select(self):
        self.menu_step = MENU_STEP_MODE
        self.refresh_status_text()

    def update_grade(self, delta: int):
        self.grade = max(1, min(6, self.grade + delta))
        self.refresh_status_text()

    def cycle_subject(self, delta: int):
        idx = SUBJECTS.index(self.subject)
        self.subject = SUBJECTS[(idx + delta) % len(SUBJECTS)]
        self.refresh_status_text()

    def cycle_difficulty(self, delta: int):
        idx = DIFFICULTY_LEVELS.index(self.difficulty)
        self.difficulty = DIFFICULTY_LEVELS[(idx + delta) % len(DIFFICULTY_LEVELS)]
        self.refresh_status_text()

    def reset_to_menu(self):
        self.game_state = STATE_MENU
        self.menu_step = MENU_STEP_MODE
        self.player_x = 0.0
        self.wall_z = self.tuning.wall_start_z
        self.message_text = ""
        self.correct_flash = 0.0
        self.wrong_flash = 0.0
        self.camera_shake = 0.0
        self.rating_target_quiz = None
        self.rating_feedback = ""
        self.refresh_status_text()

    def load_current_quiz(self):
        if self.mode == MODE_TEN:
            if self.current_index >= len(self.quiz_list):
                self.clear_game()
                return
            self.current_quiz = self.quiz_list[self.current_index]
        else:
            if not self.quiz_list:
                self.quiz_list = self.provider.get_quizzes(
                    subject=self.subject,
                    grade=self.grade,
                    difficulty=self.difficulty,
                    mode=MODE_ENDLESS,
                    count=1,
                )
            self.current_quiz = self.quiz_list[0]

        self.choice_locked = False
        self.wall_z = self.tuning.wall_start_z
        self.player_x = 0.0
        self.message_text = ""
        self.refresh_status_text()

    def update(self, dt: float, move_axis: float):
        self.correct_flash = max(0.0, self.correct_flash - dt * 1.5)
        self.wrong_flash = max(0.0, self.wrong_flash - dt * 1.2)
        self.camera_shake = max(0.0, self.camera_shake - dt * 2.8)

        if self.game_state == STATE_MENU:
            return

        if self.game_state == STATE_PRELOADING:
            self.preload_wait_sec += dt
            missing = max(0, self.target_count - len(self.quiz_list)) if self.mode == MODE_TEN else 1
            if missing > 0:
                self.quiz_list.extend(
                    self.provider.get_quizzes(
                        subject=self.subject,
                        grade=self.grade,
                        difficulty=self.difficulty,
                        mode=self.mode,
                        count=missing,
                    )
                )
            ready = (self.mode == MODE_TEN and len(self.quiz_list) >= self.target_count) or (
                self.mode == MODE_ENDLESS and len(self.quiz_list) >= 1
            )
            if ready and self.preload_wait_sec >= self.min_preload_sec:
                self.game_state = STATE_PLAYING
                self.load_current_quiz()
            else:
                self.message_text = "Loading quizzes..." if self.use_english_ui else "クイズを準備中..."
                self.refresh_status_text()
            return

        if self.game_state == STATE_PLAYING:
            self.player_x += move_axis * self.tuning.player_speed * dt
            self.player_x = max(self.tuning.min_x, min(self.tuning.max_x, self.player_x))
            self.wall_z -= self.tuning.wall_speed * dt
            if self.wall_z <= self.tuning.hit_z + 0.45:
                self.resolve_collision()
            return

        if self.game_state == STATE_CORRECT:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.advance_after_correct()

    def is_within_door(self, x_pos: float, side: int) -> bool:
        center = self.tuning.left_door_x if side == 0 else self.tuning.right_door_x
        return abs(x_pos - center) <= self.tuning.door_half_width

    def resolve_collision(self):
        if not self.current_quiz or self.choice_locked:
            return
        self.choice_locked = True

        answer = int(self.current_quiz.a)
        in_left = self.is_within_door(self.player_x, 0)
        in_right = self.is_within_door(self.player_x, 1)

        if not in_left and not in_right:
            self.game_over("Hit the wall!" if self.use_english_ui else "壁にぶつかった！")
            return
        if in_left and in_right:
            self.game_over("Cannot decide!" if self.use_english_ui else "中央で判定不能！")
            return

        selected = 0 if in_left else 1
        if selected == answer:
            self.score += 1
            self.recent_results.append(True)
            if hasattr(self.provider, "submit_result"):
                self.provider.submit_result(self.current_quiz, True)
            self.game_state = STATE_CORRECT
            self.message_timer = self.tuning.correct_hold_sec
            self.message_text = "Correct!" if self.use_english_ui else "正解！"
            self.correct_flash = 1.0
            self.camera_shake = 0.22
        else:
            self.recent_results.append(False)
            if hasattr(self.provider, "submit_result"):
                self.provider.submit_result(self.current_quiz, False)
            explain = self.current_quiz.e or ("No explanation" if self.use_english_ui else "解説なし")
            if self.use_english_ui:
                self.game_over(f"Wrong! Answer was {'Left' if answer == 0 else 'Right'}\n{explain}")
            else:
                self.game_over(f"不正解！ 正解は {'左' if answer == 0 else '右'}\n{explain}")

    def advance_after_correct(self):
        if self.mode == MODE_TEN:
            self.current_index += 1
            self.load_current_quiz()
        else:
            self.quiz_list = self.provider.get_quizzes(
                subject=self.subject,
                grade=self.grade,
                difficulty=self.difficulty,
                mode=MODE_ENDLESS,
                count=1,
            )
            self.load_current_quiz()
        self.game_state = STATE_PLAYING
        self.message_text = ""

    def game_over(self, msg: str):
        self.game_state = STATE_GAME_OVER
        self.rating_target_quiz = self.current_quiz
        self.rating_feedback = ""
        self.message_text = "GAME OVER\n\n" + msg
        self.wrong_flash = 1.0
        self.camera_shake = 0.35
        self.refresh_status_text()

    def clear_game(self):
        self.game_state = STATE_CLEAR
        self.rating_target_quiz = self.current_quiz
        self.rating_feedback = ""
        if self.use_english_ui:
            self.message_text = f"CLEAR! Congrats\n10 questions done  Score: {self.score}/10"
        else:
            self.message_text = f"CLEAR! おめでとう\n10問完走  正解数: {self.score}/10"
        self.correct_flash = 1.0
        self.refresh_status_text()

    def rate_last_question(self, good: bool):
        if not self.rating_target_quiz:
            return
        if good:
            if hasattr(self.provider, "mark_quiz_good"):
                self.provider.mark_quiz_good(
                    self.rating_target_quiz, subject=self.subject, grade=self.grade, difficulty=self.difficulty
                )
            self.rating_feedback = "Rated: Good" if self.use_english_ui else "評価: 良い問題"
        else:
            if hasattr(self.provider, "mark_quiz_bad"):
                self.provider.mark_quiz_bad(
                    self.rating_target_quiz, subject=self.subject, grade=self.grade, difficulty=self.difficulty
                )
            self.rating_feedback = "Rated: Bad" if self.use_english_ui else "評価: 悪い問題"

    def question_text(self) -> str:
        if not self.current_quiz:
            return ""
        return f"Q: {self.current_quiz.q}"

    def choices_text(self) -> tuple[str, str]:
        if not self.current_quiz:
            return "", ""
        if self.use_english_ui:
            return (
                f"Left [A]: {self.current_quiz.c[0]}",
                f"Right [D]: {self.current_quiz.c[1]}",
            )
        return (
            f"左ドア [A]: {self.current_quiz.c[0]}",
            f"右ドア [D]: {self.current_quiz.c[1]}",
        )

    def refresh_status_text(self):
        if self.game_state in (STATE_GAME_OVER, STATE_CLEAR):
            if self.use_english_ui:
                self.status_text = f"Score: {self.score}  |  Press [R] for menu"
            else:
                self.status_text = f"正解数: {self.score}  |  [R] でメニューへ戻る"
            return

        if self.game_state == STATE_MENU:
            if self.use_english_ui:
                if self.menu_step == MENU_STEP_MODE:
                    self.status_text = "Step 1/3: Select mode"
                else:
                    mode_label = "10 Q" if self.mode == MODE_TEN else "Endless"
                    self.status_text = (
                        f"Step 2/3: Set grade/subject  |  Mode:{mode_label} "
                        f"Subject:{SUBJECT_EN.get(self.subject, self.subject)} Grade:{self.grade}"
                    )
            else:
                if self.menu_step == MENU_STEP_MODE:
                    self.status_text = "手順 1/3: モードを選択"
                else:
                    mode_label = "10問チャレンジ" if self.mode == MODE_TEN else "エンドレス"
                    self.status_text = (
                        f"手順 2/3: 学年・教科を設定  |  モード:{mode_label}  "
                        f"教科:{self.subject}  学年:{self.grade}"
                    )
            return

        if self.game_state == STATE_PRELOADING:
            if self.use_english_ui:
                if self.mode == MODE_TEN:
                    self.status_text = (
                        f"Loading quizzes... {len(self.quiz_list)}/{self.target_count} "
                        f"(Subject:{SUBJECT_EN.get(self.subject, self.subject)} Grade:{self.grade})"
                    )
                else:
                    self.status_text = (
                        f"Loading quiz... buffered:{len(self.quiz_list)} "
                        f"(Subject:{SUBJECT_EN.get(self.subject, self.subject)} Grade:{self.grade})"
                    )
            else:
                if self.mode == MODE_TEN:
                    self.status_text = (
                        f"クイズ準備中... {len(self.quiz_list)}/{self.target_count} "
                        f"教科:{self.subject} 学年:{self.grade}"
                    )
                else:
                    self.status_text = f"クイズ準備中... バッファ:{len(self.quiz_list)} 教科:{self.subject} 学年:{self.grade}"
            return

        if self.use_english_ui:
            mode_label = "10 Q" if self.mode == MODE_TEN else "Endless"
            progress = f"{self.current_index + 1}/10" if self.mode == MODE_TEN else "inf"
            subj = SUBJECT_EN.get(self.subject, self.subject)
            diff = DIFFICULTY_EN.get(self.difficulty, self.difficulty)
            self.status_text = (
                f"Subject:{subj} Grade:{self.grade} Diff:{diff} Mode:{mode_label} "
                f"Progress:{progress} Score:{self.score}"
            )
        else:
            mode_label = "10問チャレンジ" if self.mode == MODE_TEN else "エンドレス"
            progress = f"{self.current_index + 1}/10" if self.mode == MODE_TEN else "∞"
            self.status_text = (
                f"教科:{self.subject}  学年:{self.grade}  難易度:{self.difficulty}  モード:{mode_label}  "
                f"進行:{progress}  正解数:{self.score}"
            )
