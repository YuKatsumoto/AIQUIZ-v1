# AIQUIZ

AI脱出クイズのリポジトリです。

## フォルダ構成

| パス | 内容 |
|------|------|
| `AIQUIZ-v1/` | Python + Pygame。`2D_pygame.py` / `game/`（3D コア）、`offline_bank.json`、LLM 連携まわり |

## 別PCで始める手順

1. **クローン**
   ```bash
   git clone https://github.com/YuKatsumoto/AIQUIZ-v1.git AIQUIZ
   cd AIQUIZ
   ```
   （リポジトリ名は GitHub 上は `AIQUIZ-v1`、中身はモノレポです。）

2. **秘密情報**
   - ルートの `.env` は **Git に含めていません**。前のPCからコピーするか、各ツールの設定で入れ直してください。

3. **Python 版（参照・実行）**
   ```bash
   cd AIQUIZ-v1
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
   エントリは `2D_pygame.py` や `3D_enginefree.py` など README なしのため、必要なら `AIQUIZ-v1/README.md` を参照。

## Git の注意

- 初回は `AIQUIZ-v1` 内のネストされた `.git` を外し、**1 本の履歴**にまとめています。
- リモート `main` は、モノレポ初回コミットに合わせるため **force-push 済み**の時期があります。古い単体 `AIQUIZ-v1` の `main` 履歴は GitHub 上では上書きされています。

## ライセンス・第三者

各エンジン・ライブラリの利用条件に従ってください。
