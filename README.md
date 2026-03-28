# AIQUIZ

AI脱出クイズのリポジトリです。**Pygame 版（2D/3D ロジックの参照元）**と **Unreal Engine 5.4 版**を同じリポジトリで管理しています。

## フォルダ構成

| パス | 内容 |
|------|------|
| `AIQUIZ-v1/` | Python + Pygame。`2D_pygame.py` / `game/`（3D コア）、`offline_bank.json`、LLM 連携まわり |
| `AIQUIZ-UE5/` | UE5.4 プロジェクト。`AIQuiz5.uproject` を開く。C++ モジュール `AIQuiz5`（クイズ状態・HTTP・UMG 相当 UI・オフラインバンク等） |

ルートの `AIQuiz5/` は使用しない断片フォルダです（`.gitignore` で無視）。

## 別PCで始める手順

1. **クローン**
   ```bash
   git clone https://github.com/YuKatsumoto/AIQUIZ-v1.git AIQUIZ
   cd AIQUIZ
   ```
   （リポジトリ名は GitHub 上は `AIQUIZ-v1`、中身はモノレポです。）

2. **秘密情報**
   - ルートの `.env` は **Git に含めていません**。前のPCからコピーするか、各ツールの設定で入れ直してください。
   - UE 側は **プロジェクト設定 → Game → AI Quiz**（`UQuizDeveloperSettings`）または `Config/DefaultGame.ini` で API キー等を設定可能です。

3. **Unreal Engine 5.4**
   - Epic Games ランチャーで **UE 5.4** をインストール。
   - `AIQUIZ-UE5/AIQuiz5.uproject` をダブルクリックで開く（初回は C++ 再生成の案内に従う）。
   - Visual Studio 2022（C++ ゲーム開発）で `AIQuiz5.sln` を生成・ビルドするか、エディタからビルド。
   - ビルドターゲット例: **AIQuiz5Editor** / Win64 / Development。

4. **Python 版（参照・実行）**
   ```bash
   cd AIQUIZ-v1
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
   エントリは `2D_pygame.py` や `3D_enginefree.py` など README なしのため、必要なら `AIQUIZ-v1/README.md` を参照。

## これまでの実装メモ（UE5 側）

- **ゲームフレーム**: `GameMode` / `GameState`、Enhanced Input、廊下・壁・Pawn などのビジュアルアクター。
- **UI**: `UQuizMainWidget` で UMG 風に動的構築（`Blueprint/WidgetTree.h`）。UE 5.4 では `ClearWidgets()` が無いため、既存 `RootWidget` を `RemoveWidget` で外してから再構築。
- **データ**: `Content/Data/offline_bank.json`（Python 版からコピー）。
- **LLM**: `FHttpModule` で OpenAI / Gemini。JSON エスケープ用ヘルパは MSVC の曖昧さ回避のため `QuizEscapeJsonForHttp` などにリネーム済み。
- **設定**: `QuizDeveloperSettings`（コンストラクタを `.cpp` に実装済み）。
- **ビルド**: `AIQuiz5.Build.cs` で `PublicIncludePaths.Add(ModuleDirectory)` により `#include "Quiz/..."` が解決。

## Git の注意

- 初回は `AIQUIZ-v1` 内のネストされた `.git` を外し、**1 本の履歴**にまとめています。
- リモート `main` は、モノレポ初回コミットに合わせるため **force-push 済み**の時期があります。古い単体 `AIQUIZ-v1` の `main` 履歴は GitHub 上では上書きされています。

## ライセンス・第三者

各エンジン・ライブラリの利用条件に従ってください。
