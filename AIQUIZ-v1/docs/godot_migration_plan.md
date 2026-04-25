# AI脱出クイズ 3D → Godot 移植計画

## 概要

現在のPython (Pygame + ModernGL) ベースの3Dクイズゲームを **Godot 4.x (GDScript)** に移植する。
Godotの組み込み3Dエンジン、UIシステム、オーディオシステムを活用し、カスタムOpenGLコードを不要にする。

## 現在のアーキテクチャ分析

### ファイル構成 (Python版)

| ファイル | 行数 | 役割 |
|---|---|---|
| `game/app/main_3d.py` | 193 | エントリポイント、ゲームループ、入力処理 |
| `game/core/game_state.py` | 638 | ゲームロジック（状態遷移、衝突判定、スコア管理） |
| `game/core/constants.py` | 21 | 定数定義 |
| `game/core/quiz_provider.py` | 522 | オフラインクイズ読込、LLMプロンプト生成 |
| `game/core/providers/buffered_provider.py` | ~400 | バックグラウンドクイズ取得 |
| `game/core/providers/online_fetch.py` | ~250 | OpenAI / Gemini API呼び出し |
| `game/core/providers/api_status.py` | ~150 | API接続状態管理 |
| `game/render/renderer.py` | 792 | ModernGL 3Dレンダリング、パーティクル |
| `game/render/math3d.py` | 85 | 3D数学ユーティリティ |
| `game/ui/hud.py` | 973 | Pygame 2D UIオーバーレイ |
| `game/audio/synth.py` | 83 | 手続き的サウンド生成 |

### ゲームメカニクス

- プレイヤーが3D廊下を前進、壁のドア（2択 or 4択）を選んでクイズに回答
- 正解→パーティクル＋次の壁、不正解→爆発アニメーション＋ゲームオーバー
- 1P: FPS視点 + マウスカメラ、2P: 俯瞰視点 + 2キャラ表示
- メニュー画面（モード選択→設定）、設定画面（API状態確認）
- 10問チャレンジ / エンドレス の2モード
- 難易度3段階（簡単/普通/難しい）、教科3種類、学年1〜6

---

## User Review Required

> [!IMPORTANT]
> **Godotバージョン**: Godot 4.3 (最新安定版) を前提にしています。別バージョン希望があれば教えてください。

> [!IMPORTANT]
> **言語選択**: GDScript を使用する計画です。C# を希望する場合はお知らせください。

> [!IMPORTANT]
> **移植範囲**: 以下の機能は移植対象外として良いですか？
> - **2Dバージョン** (`2D_pygame.py`) — 3D版のみ移植
> - **Firebase同期** — オプショナル機能のため初期スコープ外

> [!WARNING]
> **オンラインクイズ生成 (LLM API)**: Godotの `HTTPRequest` ノードで再実装しますが、Python版の `threading` ベースのバッファリングとは設計が変わります。Godotでは `await` + コルーチンベースになります。

---

## Proposed Changes

### Godotプロジェクト全体構造

```
c:\AIQUIZ\AIQUIZ-Godot\
├── project.godot                     # プロジェクト設定
├── .env                              # API キー（コピー）
├── offline_bank.json                 # クイズデータ（コピー）
├── quiz_ratings.json                 # 評価データ（コピー）
│
├── scenes/
│   ├── main.tscn                     # メインシーン（ルート）
│   ├── game_world.tscn               # 3Dゲームワールド
│   ├── player.tscn                   # プレイヤーモデル（ブロック人間）
│   ├── quiz_wall.tscn                # クイズ壁＋ドア
│   └── particle_effects.tscn         # パーティクルエフェクト
│
├── ui/
│   ├── main_menu.tscn                # メインメニュー画面
│   ├── mode_select.tscn              # モード選択UI
│   ├── config_select.tscn            # 設定（学年・教科）UI
│   ├── settings_screen.tscn          # 設定画面（API状態等）
│   ├── gameplay_hud.tscn             # ゲーム中HUD
│   ├── result_overlay.tscn           # ゲームオーバー/クリア画面
│   └── preloading_screen.tscn        # ローディング画面
│
├── scripts/
│   ├── autoload/
│   │   ├── game_manager.gd           # ゲーム全体管理（Autoload）
│   │   ├── quiz_manager.gd           # クイズデータ管理（Autoload）
│   │   └── audio_manager.gd          # オーディオ管理（Autoload）
│   │
│   ├── core/
│   │   ├── constants.gd              # 定数定義
│   │   ├── game_state.gd             # ゲーム状態ロジック
│   │   ├── quiz_item.gd              # QuizItem リソースクラス
│   │   ├── quiz_provider.gd          # オフラインプロバイダー
│   │   ├── buffered_provider.gd      # バッファ付きプロバイダー
│   │   ├── online_fetch.gd           # API呼び出し
│   │   └── api_status.gd             # API状態管理
│   │
│   ├── world/
│   │   ├── game_world.gd             # 3Dワールド管理
│   │   ├── player_controller.gd      # プレイヤー移動・入力
│   │   ├── quiz_wall_spawner.gd      # 壁生成・管理
│   │   ├── door.gd                   # ドア表示・ラベル
│   │   └── camera_controller.gd      # カメラ制御（FPS/俯瞰/爆発）
│   │
│   ├── effects/
│   │   ├── particle_spawner.gd       # パーティクルエフェクト
│   │   ├── explosion_effect.gd       # 爆発アニメーション
│   │   └── screen_effects.gd         # 画面フラッシュ・シェイク
│   │
│   └── ui/
│       ├── main_menu.gd              # メインメニューロジック
│       ├── gameplay_hud.gd           # ゲーム中HUDロジック
│       └── result_overlay.gd         # 結果画面ロジック
│
├── resources/
│   ├── materials/
│   │   ├── floor_material.tres       # 床マテリアル
│   │   ├── wall_material.tres        # 壁マテリアル
│   │   └── door_materials/           # ドア色マテリアル (青/緑/橙/赤)
│   │
│   ├── fonts/
│   │   └── (日本語フォント)
│   │
│   └── themes/
│       └── game_theme.tres           # UI テーマ
│
└── addons/                           # (必要に応じて)
```

---

### Phase 1: プロジェクト基盤 (Day 1-2)

#### [NEW] `project.godot`
- Godot 4.3 プロジェクト初期化
- 入力マップ設定 (move_left, move_right, etc.)
- ウィンドウサイズ 1280×720、リサイズ可能
- レンダラー設定 (Forward+, MSAA 4x)

#### [NEW] `scripts/autoload/game_manager.gd`
- ゲーム全体のライフサイクル管理
- シーン遷移制御
- `.env` ファイル読み込み

#### [NEW] `scripts/core/constants.gd`
- Python版 `constants.py` の移植
- 状態定数、教科・難易度リスト等

#### [NEW] `scripts/core/game_state.gd`
- Python版 `game_state.py` (638行) の移植
- `GameTuning` → Resource クラス
- `QuizGameState` → RefCounted クラス
- 全ゲームロジック（移動・衝突・状態遷移）を維持

---

### Phase 2: クイズシステム (Day 2-3)

#### [NEW] `scripts/core/quiz_item.gd`
- `QuizItem` データクラス (Resource)
- フィールド: `q`, `c`, `a`, `e`, `src`, `img`

#### [NEW] `scripts/core/quiz_provider.gd`
- `offline_bank.json` 読込
- 難易度別バケット分け
- フォールバック問題生成
- Python版 `quiz_provider.py` のロジック移植

#### [NEW] `scripts/core/buffered_provider.gd`
- Godot の `Thread` + `Mutex` を使用したバックグラウンドバッファリング
- Python版 `buffered_provider.py` の移植

#### [NEW] `scripts/core/online_fetch.gd`
- `HTTPRequest` ノードでOpenAI / Gemini API呼び出し
- Python版 `online_fetch.py` の移植
- プロンプト生成ロジック（`build_online_prompt_2d_style` 相当）

#### [NEW] `scripts/core/api_status.gd`
- API接続チェック
- Python版 `api_status.py` の移植

---

### Phase 3: 3Dワールド (Day 3-5)

#### [NEW] `scenes/game_world.tscn`
- 3D ノード構成:
  - `DirectionalLight3D` (メイン照明)
  - `Camera3D` (プレイヤーカメラ)
  - `MeshInstance3D` (床: BoxMesh)
  - ドア/壁のインスタンス化ポイント
  - `WorldEnvironment` (フォグ、アンビエント)

#### [NEW] `scripts/world/game_world.gd`
- 壁/ドアの動的生成・破棄
- ゲームワールドの状態更新
- Python版 `renderer.py` の `_draw_world` に相当

#### [NEW] `scenes/player.tscn`
- ブロック人間モデル (6パーツ: 頭/胴体/両腕/両脚)
- `MeshInstance3D` × 6 (BoxMesh) をノード階層で構成
- `AnimationPlayer` で歩行アニメーション

#### [NEW] `scripts/world/player_controller.gd`
- プレイヤー移動 (A/D + Arrow keys)
- 歩行アニメーション制御
- 爆発アニメーション（パーツ分離 + 物理）
- Python版の `_draw_player_alive` / `_draw_player_exploding` に相当

#### [NEW] `scenes/quiz_wall.tscn`
- 壁本体 + ドア (2個 or 4個) の PackedScene
- ドアラベル用 `Label3D` ノード
- ドア色マテリアル

#### [NEW] `scripts/world/quiz_wall_spawner.gd`
- 壁インスタンスの生成・位置管理
- ラベルテキスト更新

#### [NEW] `scripts/world/camera_controller.gd`
- 1P FPS視点 (マウスルック)
- 2P 俯瞰視点
- ゲームオーバー: ズームアウト + シェイク
- 正解: カメラシェイク
- Python版 `_camera()` の移植

---

### Phase 4: エフェクト (Day 5-6)

#### [NEW] `scripts/effects/particle_spawner.gd`
- 正解パーティクル (金/緑/シアン、100個)
- 爆発パーティクル (赤/オレンジ、250個)
- Godot の `GPUParticles3D` を使用

#### [NEW] `scripts/effects/screen_effects.gd`
- 画面フラッシュ (正解: 緑、不正解: 赤)
- カメラシェイク (`camera_shake` の制御)

---

### Phase 5: UI (Day 6-8)

#### [NEW] `ui/main_menu.tscn` + `scripts/ui/main_menu.gd`
- モード選択画面 (10問チャレンジ / エンドレス)
- クイック設定パネル（プレイヤー数/難易度/出題方式）
- 学年・教科選択画面
- 設定画面（API状態、壁速度、音量）
- Godot の `Control` ノードで構築 (`VBoxContainer`, `Button`, `Label` 等)
- Python版 `hud.py` のメニュー部分 (~650行) の移植

#### [NEW] `ui/gameplay_hud.tscn` + `scripts/ui/gameplay_hud.gd`
- 問題カード（上部中央）
- 選択肢ヒント（左右）
- スコア/進行表示（右上）
- プログレスバー（下部、10問モード）
- Python版 `hud.py` の `_draw_play` 部分の移植

#### [NEW] `ui/result_overlay.tscn` + `scripts/ui/result_overlay.gd`
- ゲームオーバー / クリア画面
- 評価ボタン（良い/悪い）
- メニューに戻るボタン
- フェードイン演出

#### [NEW] `ui/preloading_screen.tscn`
- ローディングアニメーション
- プログレスバー

---

### Phase 6: オーディオ (Day 8)

#### [NEW] `scripts/autoload/audio_manager.gd`
- 正解音 / 爆発音の再生管理
- 音量制御 (SFX / BGM)

> [!NOTE]
> Python版では `numpy` で手続き的にサウンドを生成していますが、Godot版では **WAVファイル** としてエクスポートしておくか、Godotの `AudioStreamGenerator` を使用するかの選択があります。
> 事前にWAVを生成して同梱する方がシンプルです。

---

### Phase 7: 統合テスト・ポリッシュ (Day 9-10)

- 全状態遷移テスト
- 1P / 2P モード動作確認
- オンラインクイズ生成テスト
- パフォーマンス最適化
- UIデザイン微調整（Godotテーマ）

---

## 移植マッピング表

| Python概念 | Godot対応 |
|---|---|
| `pygame.display` + OpenGL window | Godot ウィンドウ (project.godot) |
| `moderngl` + カスタムシェーダー | Godot 3D ノード + StandardMaterial3D |
| `numpy` 行列演算 | Godot `Transform3D`, `Vector3`, `Basis` |
| `pygame.Surface` (HUD) | Godot `CanvasLayer` + `Control` ノード |
| `pygame.font.Font` | Godot `Label`, `Label3D`, `Theme` |
| `pygame.mixer.Sound` | Godot `AudioStreamPlayer` |
| `threading.Thread` (バッファ) | Godot `Thread` + `Mutex` |
| `requests` / `urllib` (API) | Godot `HTTPRequest` ノード |
| Pygame イベントループ | Godot `_input()`, `_process()`, `_physics_process()` |
| `dataclass` (GameState) | Godot `Resource` / `RefCounted` |
| `.env` ファイル | `ConfigFile` または手動パース |

---

## Open Questions

> [!IMPORTANT]
> **Q1: Godotのインストール状況**
> PCにGodot 4.xはインストール済みですか？未インストールの場合、ダウンロードから始めます。

> [!IMPORTANT]
> **Q2: 日本語フォント**
> Godotプロジェクトに同梱する日本語フォント（例: Noto Sans JP）をダウンロードして良いですか？
> 現在のPython版はシステムフォント（メイリオ）を使用していますが、Godotではプロジェクト内にフォントを含める必要があります。

> [!IMPORTANT]
> **Q3: 移植の進め方**
> 一度に全機能を移植するか、以下のように段階的に進めるか、どちらが良いですか？
> - **段階A**: まず最低限のゲームプレイ（オフラインクイズ + 1P + 基本UI）を動かす
> - **段階B**: その後、2P、オンラインクイズ、設定画面、エフェクトを追加

---

## Verification Plan

### 自動テスト
- Godot の GDUnit4 などを使ったゲームロジックのユニットテスト
- `game_state.gd` の状態遷移テスト
- `quiz_provider.gd` のクイズ読み込みテスト

### 手動検証
1. ゲーム起動 → メニュー表示
2. モード選択 → 学年/教科選択 → ゲーム開始
3. 1Pモード: プレイヤー移動、ドア選択、正解/不正解
4. 2Pモード: 2キャラ操作、スコア別管理
5. パーティクルエフェクト、カメラシェイク
6. ゲームオーバー / クリア画面
7. オンラインクイズ生成 (API接続)
8. 設定画面操作
