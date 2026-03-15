# -*- coding: utf-8 -*-
"""
AI脱出クイズ — クイズ API サーバー (Phase 0)
- GET  /quiz/offline   : オフライン問題を1件取得（教科・学年をクエリで指定）
- POST /quiz/request  : 問題を1件または複数件取得（モード: ten / endless）
"""
import os
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from quiz_engine import (
    get_offline_questions,
    get_subjects_grades,
    offline_pick,
)

app = FastAPI(
    title="AI脱出クイズ API",
    description="Phase 0: オフライン問題の配信。ONLINE (LLM) は後続で追加予定。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- リクエスト/レスポンス ----------

class QuizRequest(BaseModel):
    """POST /quiz/request の body"""
    subject: str = Field(..., description="教科: 算数 / 理科 / 国語")
    grade: int = Field(..., ge=1, le=6, description="学年 1-6")
    difficulty: Optional[str] = Field("普通", description="難易度: 簡単 / 普通 / 難しい（Phase 0 では未使用）")
    mode: Literal["ten", "endless"] = Field("ten", description="ten=10問まとめて, endless=1問ずつ")
    count: Optional[int] = Field(None, description="取得件数。ten のときは 10、endless のときは 1")
    player_id: Optional[int] = Field(None, description="プレイヤーID（将来の履歴用）")
    use_online: bool = Field(False, description="True で LLM 出題（Phase 0 では未実装のため無視）")


class QuizItem(BaseModel):
    """問題1件（API で返す形式）"""
    q: str
    c: list[str]
    a: int
    e: str = ""
    src: str = "OFFLINE"


# ---------- エンドポイント ----------

@app.get("/")
def root():
    return {
        "service": "AI脱出クイズ API",
        "version": "0.1.0",
        "endpoints": {
            "GET /quiz/offline": "?subject=算数&grade=3&count=1",
            "POST /quiz/request": "body: subject, grade, mode, ...",
            "GET /meta/subjects": "利用可能な教科・学年一覧",
        },
    }


@app.get("/meta/subjects")
def meta_subjects():
    """利用可能な教科・学年の一覧"""
    return get_subjects_grades()


@app.get("/quiz/offline", response_model=List[QuizItem])
def get_offline(
    subject: str = Query(..., description="教科: 算数 / 理科 / 国語"),
    grade: int = Query(..., ge=1, le=6, description="学年 1-6"),
    count: int = Query(1, ge=1, le=20, description="取得件数"),
):
    """
    オフライン問題を指定教科・学年から最大 count 件取得。
    重複なしで返す（10問チャレンジ用）。
    """
    try:
        items = get_offline_questions(subject, grade, count, prefer_image=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # Pydantic 用に a が 0/1 であることを保証
    out = []
    for q in items:
        q = dict(q)
        q.setdefault("e", q.get("exp", ""))
        if "exp" in q:
            del q["exp"]
        q.setdefault("src", "OFFLINE")
        out.append(QuizItem(**q))
    return out


@app.post("/quiz/request", response_model=List[QuizItem])
def post_quiz_request(body: QuizRequest):
    """
    問題を取得する。
    - mode=ten  : count 未指定なら 10 問をまとめて返す（オフラインから重複なし）
    - mode=endless : 1 問だけ返す（オフラインからランダム1件）
    use_online=True は Phase 0 では未実装のため無視し、オフラインで返す。
    """
    if body.use_online:
        # Phase 0: ONLINE 未実装のためオフラインにフォールバック
        pass

    if body.mode == "ten":
        count = body.count if body.count is not None else 10
        count = max(1, min(20, count))
        try:
            items = get_offline_questions(
                body.subject,
                body.grade,
                count,
                prefer_image=False,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # endless: 1問
        try:
            one = offline_pick(body.subject, body.grade, prefer_image=False)
            items = [one]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    out = []
    for q in items:
        q = dict(q)
        q.setdefault("e", q.get("exp", ""))
        if "exp" in q:
            del q["exp"]
        q.setdefault("src", "OFFLINE")
        out.append(QuizItem(**q))
    return out


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("QUIZ_API_HOST", "0.0.0.0")
    port = int(os.getenv("QUIZ_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
