# -*- coding: utf-8 -*-
"""
クイズ API 用エンジン: オフラインバンクの読み込みと問題取得。
Phase 0: オフラインのみ。ONLINE (LLM) は後続で追加可能。
"""
import os
import random
import json
from typing import List, Optional

# サーバー基準のパス: プロジェクトルートの offline_bank.json を参照
def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_offline_bank(path: Optional[str] = None) -> dict:
    """offline_bank.json を読み込む。path 未指定時はプロジェクトルートのファイルを使用。"""
    if path is None:
        path = os.path.join(_project_root(), "offline_bank.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# 画像問題は Phase 0 では使わない（テキストのみ）
BUILTIN_IMAGE_QUESTIONS: dict = {}

# 評価データは Phase 0 では空（後で quiz_ratings.json を読むように拡張可能）
def _load_ratings():
    ratings_path = os.path.join(_project_root(), "quiz_ratings.json")
    if not os.path.isfile(ratings_path):
        return {"good": [], "bad": []}
    try:
        with open(ratings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"good": [], "bad": []}
    good = data.get("good", [])
    bad = data.get("bad", [])
    if not isinstance(good, list):
        good = list(good.values()) if isinstance(good, dict) else []
    if not isinstance(bad, list):
        bad = list(bad.values()) if isinstance(bad, dict) else []
    return {"good": good, "bad": bad}


def _normalize_quiz(q: dict, src: str = "OFFLINE") -> dict:
    """1問分の dict を API 用に正規化。exp -> e、src を付与。"""
    out = dict(q)
    out.pop("_local_src", None)
    if "exp" in out and "e" not in out:
        out["e"] = out.pop("exp", "")
    out.setdefault("e", "")
    out["src"] = src
    return out


def offline_pick(subject: str, grade: int, prefer_image: bool = False) -> dict:
    """
    指定教科・学年でオフライン問題を1問ランダムに選んで返す。
    """
    grade_str = str(grade)
    bank = load_offline_bank()
    arr = [
        _normalize_quiz(dict(q, _local_src="OFFLINE"), "OFFLINE")
        for q in bank.get(subject, {}).get(grade_str, [])
    ]
    image_arr = [
        _normalize_quiz(dict(q, _local_src="IMAGE"), "IMAGE")
        for q in BUILTIN_IMAGE_QUESTIONS.get(subject, {}).get(grade_str, [])
    ]
    ratings = _load_ratings()
    good_arr = [
        _normalize_quiz(dict(q, _local_src="OFFLINE"), "OFFLINE")
        for q in ratings.get("good", [])
        if isinstance(q, dict) and q.get("subject") == subject and str(q.get("grade")) == grade_str
    ]
    for item in good_arr:
        item.pop("_local_src", None)

    if prefer_image and image_arr:
        combined = image_arr + arr + good_arr
    else:
        combined = arr + image_arr + good_arr

    for item in arr + image_arr:
        item.pop("_local_src", None)

    if not combined:
        a = random.randint(2, 20)
        b = random.randint(1, 10)
        ans = a + b
        wrong = ans + random.choice([-2, -1, 1, 2])
        c = [str(ans), str(wrong)]
        random.shuffle(c)
        return {
            "q": f"たしざん {a}+{b} のこたえは？",
            "c": c,
            "a": c.index(str(ans)),
            "e": f"{a}+{b}={ans}",
            "src": "OFFLINE",
        }

    ret = random.choice(combined)
    if isinstance(ret, dict):
        ret = dict(ret)
    else:
        ret = {}
    ret.setdefault("src", "OFFLINE")
    return _normalize_quiz(ret, ret.get("src", "OFFLINE"))


def get_offline_questions(
    subject: str,
    grade: int,
    count: int,
    prefer_image: bool = False,
) -> List[dict]:
    """
    指定教科・学年でオフライン問題を最大 count 件、重複なしで返す。
    10問チャレンジ用。
    """
    grade_str = str(grade)
    bank = load_offline_bank()
    raw = list(bank.get(subject, {}).get(grade_str, []))
    image_raw = list(BUILTIN_IMAGE_QUESTIONS.get(subject, {}).get(grade_str, []))
    ratings = _load_ratings()
    good_raw = [
        q for q in ratings.get("good", [])
        if isinstance(q, dict) and q.get("subject") == subject and str(q.get("grade")) == grade_str
    ]

    combined = []
    for q in raw:
        combined.append(_normalize_quiz(dict(q), "OFFLINE"))
    for q in image_raw:
        combined.append(_normalize_quiz(dict(q), "IMAGE"))
    for q in good_raw:
        combined.append(_normalize_quiz(dict(q), "OFFLINE"))

    if not combined:
        out = []
        for _ in range(min(count, 10)):
            q = offline_pick(subject, grade, prefer_image)
            out.append(q)
        return out[:count]

    random.shuffle(combined)
    return combined[:count]


def get_subjects_grades() -> dict:
    """利用可能な教科・学年の一覧を返す（API のメタ情報用）。"""
    bank = load_offline_bank()
    return {
        subject: list(levels.keys())
        for subject, levels in bank.items()
        if isinstance(levels, dict)
    }
