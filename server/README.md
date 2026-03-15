# AI脱出クイズ — クイズ API サーバー (Phase 0)

Unreal Engine 3D 版および将来のクライアント向けに、問題を配信する REST API です。  
Phase 0 では**オフライン問題のみ**対応。ONLINE (OpenAI/Gemini) は後続で追加予定です。

## セットアップ

```bash
cd server
pip install -r requirements.txt
cp .env.example .env   # 必要に応じて編集
```

## 起動

```bash
python main.py
```

- デフォルト: `http://0.0.0.0:8000`
- 環境変数: `QUIZ_API_PORT=8000`, `QUIZ_API_HOST=0.0.0.0`

## エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/` | サービス情報・エンドポイント一覧 |
| GET | `/meta/subjects` | 利用可能な教科・学年一覧 |
| GET | `/quiz/offline` | オフライン問題を取得。クエリ: `subject`, `grade`, `count` |
| POST | `/quiz/request` | 問題を取得。body: `subject`, `grade`, `mode` (ten/endless), `count` など |

### GET /quiz/offline

- `subject`: 算数 / 理科 / 国語
- `grade`: 1〜6
- `count`: 1〜20（取得件数）

例: `GET /quiz/offline?subject=算数&grade=3&count=5`

### POST /quiz/request

Body (JSON):

```json
{
  "subject": "算数",
  "grade": 3,
  "difficulty": "普通",
  "mode": "ten",
  "count": 10,
  "use_online": false
}
```

- `mode=ten`: 10問チャレンジ用。`count` 件（未指定時 10）を重複なしで返す。
- `mode=endless`: 1問だけ返す。
- `use_online`: Phase 0 では未実装のため無視され、常にオフラインで返す。

### 問題 1 件の形式

```json
{
  "q": "問題文",
  "c": ["選択肢1", "選択肢2"],
  "a": 0,
  "e": "解説",
  "src": "OFFLINE"
}
```

- `a`: 正解のインデックス (0=左ドア, 1=右ドア)。

## データ

- 問題データは**プロジェクトルート**の `offline_bank.json` を参照します（`server/` の1つ上のフォルダ）。
- 評価データ `quiz_ratings.json` があれば「いいね」された問題を優先して出題に含めます。

## 動作確認 (Postman / curl)

```bash
# ルート
curl http://127.0.0.1:8000/

# オフライン 1 件
curl "http://127.0.0.1:8000/quiz/offline?subject=算数&grade=2&count=1"

# 10 問リクエスト
curl -X POST http://127.0.0.1:8000/quiz/request -H "Content-Type: application/json" -d "{\"subject\":\"算数\",\"grade\":3,\"mode\":\"ten\",\"count\":10}"
```

API ドキュメント（Swagger）: 起動後に `http://127.0.0.1:8000/docs` を開く。
