import json
import os
import random
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, List

from game.core.quiz_provider import QuizItem, build_online_prompt_2d_style


# A single global executor allows slow requests to be abandoned in the background
# so they do not block the worker thread on context-manager exit.
_GLOBAL_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = __import__("threading").Lock()


def _get_executor() -> ThreadPoolExecutor:
    """Return (and lazily create) the global thread pool, recreating if shut down."""
    global _GLOBAL_EXECUTOR
    with _EXECUTOR_LOCK:
        if _GLOBAL_EXECUTOR is None or _GLOBAL_EXECUTOR._shutdown:
            _GLOBAL_EXECUTOR = ThreadPoolExecutor(max_workers=6)
        return _GLOBAL_EXECUTOR


def _extract_json_from_text(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return None
    decoder = json.JSONDecoder()
    starts = []
    for ch in ("[", "{"):
        idx = text.find(ch)
        if idx != -1:
            starts.append(idx)
    if not starts:
        return None
    for start in sorted(starts):
        try:
            obj, _ = decoder.raw_decode(text[start:])
            return obj
        except Exception:
            continue
    return None


def _extract_quizzes_from_text(raw_text: str) -> list[dict]:
    obj = _extract_json_from_text(raw_text)
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        quizzes = obj.get("quizzes", [])
        if isinstance(quizzes, list):
            return [x for x in quizzes if isinstance(x, dict)]
    return []


def _normalize_single(raw: dict, src: str) -> QuizItem | None:
    if not isinstance(raw, dict):
        return None
    q = str(raw.get("q", "")).strip()
    c = raw.get("c", [])
    a = raw.get("a", None)
    e = str(raw.get("e", raw.get("exp", ""))).strip()
    img = str(raw.get("img", "")).strip()
    choice_img = raw.get("choice_img", raw.get("choiceImg", []))
    if not q or not isinstance(c, list) or len(c) not in (2, 4):
        return None
    try:
        a = int(a)
    except Exception:
        return None
    if a < 0 or a >= len(c):
        return None
    cleaned = [str(x).strip() for x in c]
    if any(not x for x in cleaned):
        return None
    if not isinstance(choice_img, list):
        choice_img = []
    return QuizItem(q=q, c=cleaned, a=a, e=e, src=src, img=img, choice_img=[str(x) for x in choice_img])


def _compose_prompt(
    subject: str,
    grade: int,
    difficulty: str,
    count: int,
    history: list[str],
    good_examples: list[dict],
    bad_examples: list[dict],
) -> str:
    return build_online_prompt_2d_style(
        subject=subject,
        grade=grade,
        difficulty=difficulty,
        count=count,
        history=history,
        good_examples=good_examples,
        bad_examples=bad_examples,
    )


def _fetch_openai(prompt: str, is_fast_mode: bool = False) -> List[QuizItem]:
    try:
        from openai import OpenAI
    except Exception:
        OpenAI = None
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        return []
    
    if is_fast_mode:
        model = os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini")
    else:
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
    client = OpenAI(api_key=api_key)
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.45,
            timeout=12,
        )
        text = r.choices[0].message.content if r.choices else ""
        quizzes = _extract_quizzes_from_text(text)
        out = []
        for q in quizzes:
            n = _normalize_single(q, "OPENAI")
            if n:
                out.append(n)
        return out
    except Exception:
        return []


def _fetch_gemini(prompt: str) -> List[QuizItem]:
    try:
        from google import genai
    except Exception:
        genai = None
    api_key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or genai is None:
        return []
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        client = genai.Client(api_key=api_key)
        cfg = {
            "temperature": 0.45,
            "response_mime_type": "application/json",
            "http_options": {"timeout": 15_000},
        }
        r = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=cfg,
        )
        text = getattr(r, "text", "") or ""
        quizzes = _extract_quizzes_from_text(text)
        out = []
        for q in quizzes:
            n = _normalize_single(q, "GEMINI")
            if n:
                out.append(n)
        return out
    except Exception:
        return []


def fetch_explanation_gemini(subject: str, grade: int, q: str, c: list[str], a: int) -> str:
    try:
        from google import genai
    except Exception:
        genai = None
    api_key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or genai is None:
        return ""
    
    prompt = f"問題: {q}\n選択肢: {', '.join(c)}\n正解: {c[a]}\nこの正解となる理由を、小学{grade}年生向けに15文字以内で簡潔に説明してください。出力は解説のテキストのみにしてください。"
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        client = genai.Client(api_key=api_key)
        r = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"temperature": 0.2, "http_options": {"timeout": 10_000}},
        )
        text = getattr(r, "text", "") or ""
        # Remove any surrounding quotes or newlines
        return text.strip().strip('"').strip("'").strip()
    except Exception:
        return ""

def fetch_quiz_from_online_llms_parallel(
    subject: str,
    grade: int,
    difficulty: str,
    count: int,
    include_image: bool = True,
    history: list[str] | None = None,
    good_examples: list[dict] | None = None,
    bad_examples: list[dict] | None = None,
    first_wait_seconds: float = 6.0,
    split_wait_seconds: float = -1.0,
) -> List[QuizItem]:
    if split_wait_seconds < 0:
        # Default to env variable if not explicitly passed
        split_wait_seconds = float(os.getenv("LLM_SPLIT_WAIT_SECONDS", "3.0"))

    _ = include_image
    prompt = _compose_prompt(
        subject=subject,
        grade=grade,
        difficulty=difficulty,
        count=count,
        history=history or [],
        good_examples=good_examples or [],
        bad_examples=bad_examples or [],
    )
    
    executor = _get_executor()
    f1 = executor.submit(_fetch_openai, prompt, False)  # Normal GPT
    f2 = executor.submit(_fetch_gemini, prompt)         # Gemini
    f3 = executor.submit(_fetch_openai, prompt, True)   # Fast GPT (Mini)
    
    done, pending = wait([f1, f2, f3], return_when=FIRST_COMPLETED, timeout=max(0.2, first_wait_seconds))
    results: List[QuizItem] = []
    
    for f in done:
        try:
            results.extend(f.result() or [])
        except Exception:
            pass
            
    if pending:
        done2, _ = wait(pending, timeout=max(0.0, split_wait_seconds))
        for f in done2:
            try:
                results.extend(f.result() or [])
            except Exception:
                pass
                
    unique = []
    seen = set()
    for q in results:
        if q.q in seen:
            continue
        seen.add(q.q)
        unique.append(q)
    
    # Shuffle so that ChatGPT and Gemini questions are interleaved
    random.shuffle(unique)
    return unique
