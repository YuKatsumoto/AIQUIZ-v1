import json
import time
from pathlib import Path
from typing import Any, Dict

from game.core.quiz_provider import QuizItem


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def append_generation_reject_log(
    reject_log_path: Path,
    quiz: QuizItem,
    subject: str,
    grade: int,
    difficulty: str,
    reason: str,
) -> None:
    _append_jsonl(
        reject_log_path,
        {
            "t": int(time.time()),
            "player": 1,
            "subject": subject,
            "grade": grade,
            "difficulty": difficulty,
            "reason": reason,
            "q": quiz.q,
            "src": quiz.src,
        },
    )


def append_generation_source_log(
    source_log_path: Path,
    quiz: QuizItem,
    subject: str,
    grade: int,
    difficulty: str,
) -> None:
    _append_jsonl(
        source_log_path,
        {
            "t": int(time.time()),
            "player": 1,
            "subject": subject,
            "grade": grade,
            "difficulty": difficulty,
            "q": quiz.q,
            "src": quiz.src,
        },
    )


def load_quiz_ratings(ratings_path: Path) -> Dict[str, Any]:
    try:
        with ratings_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("good", [])
            data.setdefault("bad", [])
            return data
    except Exception:
        pass
    return {"good": [], "bad": []}


def is_bad_rated_question(ratings: Dict[str, Any], quiz: QuizItem, subject: str, grade: int) -> bool:
    for item in ratings.get("bad", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("q", "")).strip() != quiz.q.strip():
            continue
        item_subject = str(item.get("subject", "")).strip()
        if item_subject and item_subject != subject:
            continue
        grade_raw = item.get("grade")
        if grade_raw is not None and str(grade_raw).strip() and str(grade_raw).strip() != str(grade):
            continue
        return True
    return False
