# Phase 1 移行まとめ — 別PCへのセットアップ用

別PCに Phase 1 の作業を移行する際のチェックリストとまとめです。

---

## 1. 必要な環境（移行先PC）

| 項目 | 要件 |
|------|------|
| **OS** | Windows 10 以降 |
| **Unreal Engine** | UE 5.4 ～ 5.7（5.7 で動作確認済み） |
| **Visual Studio** | 2022、ワークロード「C++ によるゲーム開発」 |
| **Python** | クイズ API サーバー用（Phase 0）。3.9 以降推奨 |

---

## 2. 移行するフォルダ・ファイル

### 必須（プロジェクト本体）

```
AIQUIZ/
├── AIQuizUE/
│   └── AIQUIZUE/
│       ├── AIQUIZUE.uproject          ← プロジェクト
│       ├── Source/
│       │   └── AIQUIZUE/
│       │       ├── AIQUIZUE.Build.cs
│       │       ├── AIQUIZUE.h
│       │       ├── Variant_Quiz/       ← Phase 1 の C++
│       │       │   ├── QuizTypes.h
│       │       │   ├── QuizApiSubsystem.h
│       │       │   ├── QuizApiSubsystem.cpp
│       │       │   ├── QuizWall.h
│       │       │   ├── QuizWall.cpp
│       │       │   ├── QuizGameMode.h
│       │       │   ├── QuizGameMode.cpp
│       │       │   ├── QuizWidget.h
│       │       │   ├── QuizWidget.cpp
│       │       │   ├── QuizCharacter.h
│       │       │   └── QuizCharacter.cpp
│       │       └── （既存の Variant_* フォルダ）
│       └── Content/                   ← ブループリント・レベル（.uasset）
│           └── （作成した WBP_Quiz, BP_QuizWall, BP_QuizGameMode, BP_QuizCharacter, 廊下レベル）
└── docs/
    ├── UE3D_Phase1_全体像.md
    ├── UE3D_Phase1_実装手順.md
    ├── UE3D_Phase1_セットアップ手順.md
    └── UE3D_Phase1_超詳細手順書.md
```

### 任意（クイズ API サーバー用）

- `server/` — Phase 0 の API サーバー（問題取得用）
- `offline_bank.json` — オフライン用フォールバック問題

---

## 3. 移行しないほうがよいもの

以下はビルド成果物・キャッシュなので、移行先で再生成します。

| フォルダ | 理由 |
|----------|------|
| `AIQuizUE/AIQUIZUE/Binaries/` | ビルドで再生成 |
| `AIQuizUE/AIQUIZUE/Intermediate/` | ビルドで再生成 |
| `AIQuizUE/AIQUIZUE/Saved/` | ローカル設定・ログ。新規生成でよい |
| `AIQuizUE/AIQUIZUE/.vs/` | VS ワークスペース。再生成でよい |

**移行するのは**: `Source/`、`Content/`、`Config/`、`.uproject` など、**ソースとコンテンツ**を中心に。

---

## 4. Build.cs の必須モジュール（確認用）

`Source/AIQUIZUE/AIQUIZUE.Build.cs` に以下が入っているか確認:

```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "Core",
    "CoreUObject",
    "Engine",
    "HTTP",           // ← Phase 1 用
    "Json",           // ← Phase 1 用
    "JsonUtilities",  // ← Phase 1 用
    // ... 既存の InputCore, EnhancedInput, UMG など
});
```

---

## 5. 移行先PCでの手順（簡潔版）

1. **プロジェクト一式をコピー**  
   - `AIQUIZ` フォルダ全体、または `AIQuizUE` 以下を新しいPCへコピー。

2. **Unreal Editor で開く**  
   - `AIQUIZUE.uproject` をダブルクリック。  
   - エンジンが未インストールなら、Epic Games Launcher で同じバージョンをインストール。

3. **プロジェクトファイル再生成（必要な場合）**  
   - `.uproject` を右クリック → **Visual Studio 用プロジェクトファイルを生成**。

4. **ビルド**  
   - エディタ: **ツール → コンパイル**（または Ctrl+Alt+F11）  
   - または Visual Studio で `.sln` を開いてビルド。

5. **Content が未作成なら**  
   - `docs/UE3D_Phase1_超詳細手順書.md` に従い、  
     WBP_Quiz、BP_QuizWall、BP_QuizGameMode、BP_QuizCharacter、廊下レベルを作成。

6. **API サーバー（任意）**  
   - `server/` があれば `python main.py` で起動。  
   - なければオフライン用フォールバック問題で動作するよう C++ に組み込み済み。

---

## 6. Phase 1 の機能一覧（実装済み）

| 機能 | 実装 | 備考 |
|------|------|------|
| クイズ問題取得 | `UQuizApiSubsystem` | `POST /quiz/request`、失敗時フォールバック |
| 問題・選択肢表示 | `UQuizWidget` | C++ でテキスト自動作成（WBP_Quiz は親クラスだけ指定すればよい） |
| 壁の移動 | `AQuizWall` | 手前（-X）方向に一定速度で移動 |
| 左・右ドア / 壁の当たり判定 | `AQuizWall` | Overlap で OnPlayerHitDoor(0/1)、OnPlayerHitWall |
| 正解 / 不正解 / ゲームオーバー | `AQuizGameMode` | 状態管理、1問ループ |
| 左右移動のみ | `AQuizCharacter` | DoMove で前後入力を無効化 |

---

## 7. ドキュメント参照

| ドキュメント | 用途 |
|--------------|------|
| `UE3D_Phase1_全体像.md` | Phase 1 の目標・完成イメージ・やること一覧 |
| `UE3D_Phase1_実装手順.md` | 実装のステップ順（Step 0～10） |
| `UE3D_Phase1_セットアップ手順.md` | ビルド〜ブループリント〜レベルの手順 |
| `UE3D_Phase1_超詳細手順書.md` | 1クリック単位の超詳細手順 |

---

## 8. トラブルシューティング（移行時）

| 症状 | 対処 |
|------|------|
| エンジンが見つからない | Epic Launcher で同じバージョンの UE をインストール |
| HTTP/Json エラー | Build.cs にモジュールがあるか確認。再生成→ビルド |
| ブループリントが開かない | Content フォルダごとコピーしたか確認。破損なら再作成 |
| API 接続できない | サーバー起動、`http://127.0.0.1:8000`。未起動でもフォールバックで動作 |
| Live Coding でクラッシュ | エディタを閉じ、VS でフルビルドしてから開き直す |

---

## 9. チェックリスト（移行完了確認）

- [ ] `AIQUIZUE.uproject` が開ける
- [ ] ビルドが成功する（エラーなし）
- [ ] クラス ビューアで `QuizWall`、`QuizGameMode`、`QuizWidget`、`QuizCharacter` が表示される
- [ ] WBP_Quiz、BP_QuizWall、BP_QuizGameMode、BP_QuizCharacter が存在する
- [ ] 廊下レベルが存在し、BP_QuizWall が配置されている
- [ ] ワールド設定でゲームモード = BP_QuizGameMode、ポーン = BP_QuizCharacter になっている
- [ ] プレイで問題文・選択肢が表示され、壁が動く
- [ ] 正解ドアで「正解」→ 次の問題、不正解/壁で「ゲームオーバー」になる

---

以上が Phase 1 移行のまとめです。不明点は各ドキュメントを参照してください。
