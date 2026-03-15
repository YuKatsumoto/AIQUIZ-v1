# GitHub を使った Phase 1 移行手順

このドキュメントでは、AIQUIZ プロジェクト（UE Phase 1 含む）を **GitHub** 経由で別PCに移行する方法を説明します。

---

## 前提

| 項目 | 内容 |
|------|------|
| **移行元** | 現在作業中の PC（AIQUIZ フォルダがある環境） |
| **移行先** | 新しい PC |
| **Git** | 両方の PC に Git がインストールされていること |
| **GitHub** | GitHub アカウントがあること（[github.com](https://github.com) で無料作成可） |

---

## Part A: 移行元 PC での作業（今の PC）

### Step A-1. Git のインストール確認

1. **PowerShell** または **コマンド プロンプト** を開く
2. 次を実行:
   ```bash
   git --version
   ```
3. `git version 2.x.x` のように表示されれば OK。未インストールの場合は [git-scm.com](https://git-scm.com/) からインストール

---

### Step A-2. .gitignore を作成

プロジェクトルート（`AIQUIZ` フォルダ）に `.gitignore` を作成し、**ビルド成果物やキャッシュを除外**します。これによりリポジトリが巨大になるのを防ぎます。

**作成場所**: `C:\Users\あなたの名前\Desktop\AIQUIZ\.gitignore`

**内容**（以下をそのままコピーして保存）:

```
# Unreal Engine
AIQuizUE/AIQUIZUE/Binaries/
AIQuizUE/AIQUIZUE/Intermediate/
AIQuizUE/AIQUIZUE/Saved/
AIQuizUE/AIQUIZUE/DerivedDataCache/
AIQuizUE/AIQUIZUE/.vs/
*.sln
*.suo
*.opensdf
*.sdf
*.VC.db
*.VC.opendb

# Visual Studio
.vs/
*.user
*.userosscache
*.sln.docstates

# Python
__pycache__/
*.py[cod]
*$py.class
.env
venv/
.venv/

# その他
*.log
.DS_Store
Thumbs.db
```

**注意**: `Content/` フォルダは **含める** 想定です。Blu eprint（.uasset）やレベル（.umap）は Git で管理するため、リポジトリサイズが大きくなる場合があります。Content を除外したい場合は以下を追加:

```
# Content を除外する場合（Blueprint・レベルを新PCで作り直す場合）
# AIQuizUE/AIQUIZUE/Content/
```

---

### Step A-3. リポジトリを初期化してコミット

1. **PowerShell** を開き、AIQUIZ フォルダに移動:
   ```powershell
   cd C:\Users\あなたの名前\Desktop\AIQUIZ
   ```

2. **Git リポジトリを初期化**:
   ```powershell
   git init
   ```

3. **全ファイルをステージング**:
   ```powershell
   git add .
   ```

4. **コミット**:
   ```powershell
   git commit -m "Phase 1: UE クイズゲーム 初回コミット"
   ```

5. **ブランチ名を main に**（GitHub のデフォルトに合わせる）:
   ```powershell
   git branch -M main
   ```

---

### Step A-4. GitHub にリポジトリを作成

1. ブラウザで [https://github.com/new](https://github.com/new) を開く
2. **Repository name** に `AIQUIZ` など好きな名前を入力
3. **Public** を選択（Private でも可）
4. **「Add a README file」にはチェックを入れない**（既にローカルにコードがあるため）
5. **Create repository** をクリック

6. 作成後、表示される **「…or push an existing repository from the command line」** のコマンドをメモ。例:
   ```
   git remote add origin https://github.com/あなたのユーザー名/AIQUIZ.git
   git push -u origin main
   ```

---

### Step A-5. GitHub にプッシュ

1. ローカルリポジトリにリモートを登録（URL は上でメモしたものに置き換え）:
   ```powershell
   git remote add origin https://github.com/あなたのユーザー名/AIQUIZ.git
   ```

2. **プッシュ**:
   ```powershell
   git push -u origin main
   ```

3. **GitHub にログイン**を求められたら、ブラウザまたはコマンドラインで認証する
   - HTTPS の場合: ユーザー名 + パーソナルアクセストークン（PAT）
   - PAT 作成: GitHub → Settings → Developer settings → Personal access tokens

4. プッシュが成功すると、GitHub のリポジトリページにファイル一覧が表示されます

---

### Step A-6. （任意）Content が大きい場合の Git LFS

`.uasset` や `.umap` はバイナリでサイズが大きくなることがあります。100MB を超えるファイルがあると GitHub が拒否する場合があります。

**対処**: Git LFS（Large File Storage）を使う

1. **Git LFS をインストール**:
   - [git-lfs.com](https://git-lfs.com/) からインストール
   - または: `git lfs install`

2. **LFS で追跡するファイルタイプを指定**（プロジェクトルートで実行）:
   ```powershell
   git lfs install
   git lfs track "*.uasset"
   git lfs track "*.umap"
   git add .gitattributes
   git commit -m "Add Git LFS for .uasset and .umap"
   git push
   ```

3. `.gitattributes` が作成され、大きなバイナリが LFS で管理されます

---

## Part B: 移行先 PC での作業（新しい PC）

### Step B-1. 必要なソフトをインストール

1. **Git**（[git-scm.com](https://git-scm.com/)）
2. **Unreal Engine 5.7**（またはプロジェクトで使っているバージョン）  
   - Epic Games Launcher からインストール
3. **Visual Studio 2022**（「C++ によるゲーム開発」ワークロード）
4. **Git LFS**（Part A で LFS を使った場合のみ）: `git lfs install`

---

### Step B-2. リポジトリをクローン

1. **PowerShell** または **コマンド プロンプト** を開く
2. クローンしたいフォルダに移動（例: デスクトップ）:
   ```powershell
   cd C:\Users\新しいPCのユーザー名\Desktop
   ```

3. **クローン**（URL は GitHub のリポジトリページで確認）:
   ```powershell
   git clone https://github.com/あなたのユーザー名/AIQUIZ.git
   ```

4. 完了すると `AIQUIZ` フォルダが作成される:
   ```
   C:\Users\新しいPCのユーザー名\Desktop\AIQUIZ\
   ├── .git/
   ├── AIQuizUE/
   ├── docs/
   └── （その他のファイル）
   ```

5. **LFS を使った場合**、大きなファイルが別途取得される。未取得なら:
   ```powershell
   cd AIQUIZ
   git lfs pull
   ```

---

### Step B-3. プロジェクトを開いてビルド

1. `AIQuizUE\AIQUIZUE\AIQUIZUE.uproject` を **ダブルクリック** して Unreal Editor を起動
2. エンジンバージョンが違う場合、**「バイナリが見つかりません」** と出たら:
   - `.uproject` を右クリック → **プロジェクトファイルを再生成** または **Visual Studio 用プロジェクトファイルを生成**
3. エディタで **ツール → コンパイル**（または Ctrl+Alt+F11）でビルド
4. ビルドが成功すれば、**クラス ビューア** で `QuizWall` などが表示されることを確認

---

### Step B-4. Content が含まれていなかった場合

`.gitignore` で `Content/` を除外してクローンした場合、ブループリントやレベルは含まれていません。その場合は **`docs/UE3D_Phase1_超詳細手順書.md`** に従い、以下を手動で作成してください:

- WBP_Quiz
- BP_QuizWall
- BP_QuizGameMode
- BP_QuizCharacter
- 廊下レベル

---

### Step B-5. 動作確認

1. エディタで **プレイ** を実行
2. 問題文・選択肢が表示され、壁が動くか確認
3. 正解ドアで「正解」→ 次問、不正解/壁で「ゲームオーバー」になるか確認

---

## よくある質問

### Q. 既に GitHub に別のリポジトリがある場合は？

既存のリポジトリにプッシュする場合:
```powershell
git remote add origin https://github.com/あなたのユーザー名/既存リポジトリ名.git
git push -u origin main
```
既存の `main` と履歴が異なる場合は `git pull origin main --allow-unrelated-histories` でマージしてから `git push` してください。

### Q. 認証エラー（403, 401）が出る

- **HTTPS**: GitHub の **Personal Access Token** をパスワード代わりに使う
- **SSH**: `git remote set-url origin git@github.com:ユーザー名/AIQUIZ.git` で SSH に切り替え

### Q. Content を後から追加したい

1. `.gitignore` から `Content/` の除外行を削除またはコメントアウト
2. `git add AIQuizUE/AIQUIZUE/Content/`
3. `git commit -m "Add Content"`
4. `git push`

### Q. 複数人で開発する場合

- `git pull` で最新を取得してから編集
- コンフリクト時は `.uasset` のマージが難しいため、片方の変更を採用するか、手動で再作成

### Q. 「Permission denied」や「.vsidx」で git add が失敗する

- **原因**: `.vs` フォルダ（Visual Studio のキャッシュ）が Git の対象になっており、ファイルがロックされている
- **対処**:
  1. プロジェクトルートに **`.gitignore`** があるか確認し、`.vs/` と `*.vsidx` が含まれているか確認
  2. 既に `.vs` を add してしまった場合は、インデックスから外す:
     ```powershell
     git rm -r --cached "AIQuizUE/AIQUIZUE/.vs/" 2>$null; git add .
     ```
  3. **Visual Studio や Unreal Editor をいったん閉じてから** `git add .` を実行する

### Q. 「LF will be replaced by CRLF」と警告が出る

- 改行コードの自動変換の通知です。**エラーではない**ので無視してよい
- 警告を出さないようにするには: `git config core.autocrlf true`（Windows では一般的）

---

## 移行完了チェックリスト

- [ ] 移行元: Git init → add → commit → push が成功した
- [ ] GitHub のリポジトリページにファイルが表示されている
- [ ] 移行先: git clone が成功した
- [ ] 移行先: .uproject が開ける
- [ ] 移行先: ビルドが成功する
- [ ] 移行先: プレイで問題表示・壁の動き・正解/ゲームオーバーが動作する

---

以上の手順で、GitHub を使った Phase 1 の移行が完了します。不明点は `UE3D_Phase1_移行まとめ.md` や各ドキュメントも参照してください。
