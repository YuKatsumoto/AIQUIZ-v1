import re
from collections import deque
from typing import Deque

from game.core.quiz_provider import QuizItem


def _math_grade_fit_score(text: str, grade: int) -> float:
    score = 0.55
    num_count = len(re.findall(r"\d", text))
    score += min(0.25, num_count * 0.02)
    if grade >= 5 and any(k in text for k in ["割合", "速さ", "体積", "比"]):
        score += 0.2
    if grade <= 2 and re.search(r"\d{3,}", text):
        score -= 0.25
    return max(0.0, min(1.0, score))


def _science_grade_fit_score(text: str, grade: int) -> float:
    score = 0.55
    if any(k in text for k in ["実験", "観察", "原因", "結果"]):
        score += 0.15
    if grade >= 5 and any(k in text for k in ["電磁石", "水溶液", "燃焼", "光合成"]):
        score += 0.2
    return max(0.0, min(1.0, score))


def _japanese_grade_fit_score(text: str, grade: int) -> float:
    score = 0.55
    if any(k in text for k in ["語句", "文法", "敬語"]):
        score += 0.12
    if grade >= 5 and any(k in text for k in ["四字熟語", "古典", "比喩", "短歌", "俳句"]):
        score += 0.2
    return max(0.0, min(1.0, score))


def grade_fit_reject_reason(
    quiz: QuizItem,
    subject: str,
    grade: int,
    difficulty: str = "普通",
    threshold_relax: float = 0.0,
) -> str:
    text = f"{quiz.q} {' '.join(quiz.c)} {quiz.e}"
    if subject == "算数":
        score = _math_grade_fit_score(text, grade)
    elif subject == "理科":
        score = _science_grade_fit_score(text, grade)
    else:
        score = _japanese_grade_fit_score(text, grade)
    base = 0.52
    if difficulty == "簡単":
        base -= 0.05
    elif difficulty == "難しい":
        base += 0.05
    threshold = max(0.28, base - threshold_relax)
    if score < threshold:
        return f"grade_fit_low:{score:.2f}<{threshold:.2f}"
    if grade <= 2 and any(tok in text for tok in ["方程式", "一次関数", "二次方程式"]):
        return "topic_too_advanced_low_grade"
    if grade >= 5 and any(tok in text for tok in ["ひらがな", "カタカナ"]):
        return "topic_too_easy_upper_grade"
    return ""


def _normalize_q(q: str) -> str:
    return re.sub(r"\s+", "", q or "").lower()


def _question_pattern_key(q: str) -> str:
    s = _normalize_q(q)
    s = re.sub(r"\d+", "#", s)
    s = re.sub(r"[、。,.!?！？]", "", s)
    return s


def _char_bigram_set(s: str) -> set[str]:
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def is_similar_question(quiz: QuizItem, recent_questions: Deque[str]) -> bool:
    q_norm = _normalize_q(quiz.q)
    q_pat = _question_pattern_key(quiz.q)
    q_bi = _char_bigram_set(q_pat)
    for q in recent_questions:
        q2 = _normalize_q(q)
        q2_pat = _question_pattern_key(q)
        if q_norm == q2:
            return True
        if q_pat and q2_pat and q_pat == q2_pat:
            return True
        if q_norm and q2 and (q_norm in q2 or q2 in q_norm):
            return True
        q2_bi = _char_bigram_set(q2_pat)
        if q_bi and q2_bi:
            inter = len(q_bi & q2_bi)
            uni = len(q_bi | q2_bi)
            if uni > 0 and inter / uni >= 0.84:
                return True
    return False


def push_recent_question(recent_questions: Deque[str], quiz: QuizItem, maxlen: int = 80) -> None:
    if not isinstance(recent_questions, deque):
        return
    recent_questions.append(quiz.q)
    while len(recent_questions) > maxlen:
        recent_questions.popleft()
