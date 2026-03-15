# Phase 1 実装手順 — UE でやること（ステップ順）

UE5 でエディタを開きながら、この手順に沿って進めてください。  
**前提**: クイズ API サーバー（Phase 0）を `http://127.0.0.1:8000` で起動しておく。

---

## Step 0: 準備

- **Unreal Engine 5**（5.4 または 5.5 等の安定版）をインストール。
- **プロジェクト**: 「New Project」→ **Third Person** または **Blank** を選択。  
  - **C++** で作成（API 用の C++ コードを追加するため）。プロジェクト名は例: `AIQuizUE`。

### プロジェクトの保存場所（どこに作るか）

**推奨（A）: デスクトップなど、AIQUIZPY避難所の「外」に作る**

- 例: `C:\Users\あなたの名前\Desktop\AIQuizUE`
- または: `D:\Games\AIQuizUE` など、任意のドライブ・フォルダ。
- **メリット**: UE の Content / Binaries が大きくても、Pygame 用フォルダと分かれて管理しやすい。Epic Launcher で「プロジェクトの場所」を指定するときも分かりやすい。
- クイズ API 用の C++ は、**AIQUIZPY避難所\UnrealSource\** にあるファイルを、このプロジェクトの `Source/AIQuizUE/` に**コピー**して使う（[UnrealSource/README.md](../../UnrealSource/README.md) 参照）。

**別案（B）: AIQUIZPY避難所の「中」に作る**

- 例: `C:\Users\あなたの名前\Desktop\AIQUIZPY避難所\AIQuizUE`
- **メリット**: サーバー・2D 版・ドキュメント・UE を 1 つのフォルダ（または 1 つの git リポジトリ）でまとめられる。
- **注意**: UE の `Content`・`Binaries`・`Intermediate`・`Saved` は容量が大きいので、git を使う場合は `.gitignore` に追加することを推奨。  
  UnrealSource のファイルは「この AIQuizUE 内の Source にコピー」する運用でよい。

**結論**: 特にこだわりがなければ **（A）デスクトップなど別フォルダに AIQuizUE を作る** とよい。

---

## Step 1: レベル（廊下）を作る

1. **レベルを開く**: デフォルトの `Map` をそのまま使うか、新規 Level を作成。
2. **廊下の形**:
   - **方法 A**: BSP で「Box」を伸ばして廊下状にする。  
     例: 幅 400、高さ 300、奥行き 2000 の直方体の内側が廊下になるよう、床・天井・左右壁を配置。
   - **方法 B**: シンプルな床（Plane や Cube を Scale）を 1 枚置き、左右に壁用の Cube を並べ、天井は省略しても可。
3. **向きの約束**:
   - プレイヤーが立つ場所を「手前」、壁が現れる方を「奥」とする。  
   - Unreal の座標で「奥」を **+X** または **+Y** のどちらかに統一するとわかりやすい（例: 奥 = +X）。
4. **プレイヤー開始位置**: プレイヤー Start を廊下の手前に配置。カメラが廊下の奥を見るようにする。

---

## Step 2: 壁ブループリント（BP_Wall）を作る

1. **Blueprint Class** で **Actor** を親にした `BP_Wall` を作成。
2. **コンポーネント**:
   - **Scene** (Root)
   - **Static Mesh** または **Cube**: 壁本体（厚みあり）。例: 幅 800、高さ 400、奥行き 50。
   - **左ドア用**: 壁に開けた穴の位置に、別の **Box Collision**（Overlap で反応）を置く。名前は `DoorLeft`。  
     - このコリジョンの **Tag** を `Door` にし、**Detail で変数** `DoorIndex = 0` を追加（後で判定に使う）。
   - **右ドア用**: 同様に `DoorRight`、`DoorIndex = 1`。
   - **壁本体用**: ドア以外の部分に触れたらゲームオーバーにするため、壁本体用の **Box Collision** を 1 つ置く。Tag は `WallBody`。
3. **コリジョン設定**:
   - すべて **Block** ではなく **Overlap** にし、プレイヤーと Overlap したときにイベントで判定する。
   - プレイヤーのコリジョンと「Overlap」するようにする。

※ ドアを「見た目」で分けたい場合は、壁メッシュに穴を開け、その位置にドア用コリジョンを合わせる。

---

## Step 3: 壁の移動（BP_Wall の Event Tick）

1. `BP_Wall` を開く。
2. **変数** を追加:
   - `WallSpeed` (Float): 例 200（毎秒 200 ユニット手前に移動）。
   - `bMoving` (Boolean): 壁を動かすかどうか。初期値 false。
3. **Event Tick** で:
   - `bMoving` が true のときだけ、**Get Actor Location** → **Add (X または Y を負方向に Speed * DeltaSeconds)** → **Set Actor Location**。
   - 奥を +X にした場合は、手前方向が -X なので、`Location.X -= WallSpeed * DeltaSeconds` のようにする。
4. **リセット用**: 関数 `ResetWall` を作り、壁の位置を「奥の初期位置」に戻す。初期位置は変数 `InitialLocation` (Vector) に **Event BeginPlay** で保存しておく。
5. **開始用**: 関数 `StartMoving` で `bMoving = true` にする。問題表示後にゲーム側から呼ぶ。

---

## Step 4: プレイヤー（左右移動のみ）

1. **Third Person** テンプレートなら、既存の **Character** Blueprint を複製して `BP_QuizPlayer` などにする。
2. **入力**:
   - 前後移動を無効にする: **Input Axis (Move Forward/Backward)** の Scale を 0 にするか、その入力で **Add Movement Input** を呼ばないようにする。
   - 左右のみ: **Move Right** の入力で **Add Movement Input** を Right 方向に渡す（キーボード A/D、スティック左右）。
3. **カメラ**: プレイヤー後方から廊下の奥が見えるように、Spring Arm と Camera の角度・距離を調整。
4. **コリジョン**: プレイヤー Capsule が壁・ドアのコリジョンと **Overlap** するように、Capsule の Collision Preset を「OverlapAllDynamic」などに変更するか、壁側を Overlap に合わせる。

---

## Step 5: 当たり判定（壁・ドアに触れたら）

1. **方法 A: 壁側で判定**
   - `BP_Wall` の各コリジョン（DoorLeft, DoorRight, WallBody）で **Event ActorBeginOverlap**。
   - Other Actor がプレイヤーかどうか（**Get Class** で Character か、または Tag で判定）。
   - プレイヤーなら:
     - **WallBody** → ゲームオーバーをゲームモード（または GameInstance）に通知。
     - **DoorLeft** → 選択 0 を通知。
     - **DoorRight** → 選択 1 を通知。
   - 通知は **Custom Event**、**Interface**、または **GameMode / GameState の関数を呼ぶ**のいずれかで実装。

2. **方法 B: プレイヤー側で判定**
   - プレイヤーで **Event ActorBeginOverlap**。Overlapping したのが壁のどのコリジョンかは、Overlap した Actor が BP_Wall で、その子コンポーネントの Tag や変数（DoorIndex）で判別。  
     → 壁の Blueprint に「このコリジョンは DoorIndex 0」を持たせ、Overlap 時に親 Actor からその情報を取れるようにする。

3. **ゲーム側で保持するもの**:
   - 現在の正解インデックス `AnswerIndex` (0 or 1)。
   - ドアから通知された `Choice` (0 or 1) と比較し、`Choice == AnswerIndex` なら正解、そうでなければ不正解。壁接触ならゲームオーバー。

---

## Step 6: 問題の取得（API）

- **C++ を使う場合**: リポジトリの `UnrealSource/` 以下にある **Quiz Api Subsystem** をプロジェクトにコピーし、ビルドする（後述）。
- **Blueprint のみの場合**:
  1. **HTTP Request** ノード: URL `http://127.0.0.1:8000/quiz/request`、Verb = **Post**。
  2. **Headers**: `Content-Type` = `application/json`。
  3. **Body**:  
     `{"subject":"算数","grade":3,"mode":"endless","count":1}` のような JSON 文字列。
  4. **On Success**: レスポンスの文字列を **Parse JSON**（Json Blueprint Utilities またはプラグイン）でパース。  
     返りは配列なので **[0]** を取る。その中から `q`, `c`, `a` を取得。
  5. **On Fail**: オフライン用フォールバック（ローカルで固定 1 問を持つ）でも可。

C++ サブシステムを使う場合は、GameInstance から `GetSubsystem<UQuizApiSubsystem>()->RequestQuiz(TEXT("算数"), 3, OnComplete)` のように呼び、コールバックで `FQuizItem` を受け取る。

---

## Step 7: 問題の表示（UMG）

1. **Widget Blueprint** を新規作成（例: `WBP_Quiz`）。
2. **コントロール**:
   - 問題文用 **Text**（変数名 `Text_Question`）。
   - 左の選択肢用 **Text**（`Text_ChoiceLeft`）。
   - 右の選択肢用 **Text**（`Text_ChoiceRight`）。
3. **関数**: `SetQuiz(FString Question, FString Choice0, FString Choice1)` を作り、上記 3 つの Text に Set Text する。
4. ゲーム開始時または問題取得後に、API で得た `q`, `c[0]`, `c[1]` で `SetQuiz` を呼ぶ。
5. この Widget を **Viewport** に Add to Viewport（ゲーム中ずっと表示）。

---

## Step 8: ゲーム状態と 1 問ループ

1. **GameMode** を Blueprint で拡張（例: `BP_QuizGameMode`）。  
   ここで「現在の問題」「状態」「正解インデックス」を持つ。
2. **状態**（Enum または Integer）:
   - **Loading**: 問題取得中。
   - **Playing**: 壁が動いている。プレイヤーがドア/壁に触れるのを待つ。
   - **Correct**: 正解表示中（1〜2 秒後に次の問題へ）。
   - **GameOver**: ゲームオーバー表示中。
3. **流れ**:
   - **BeginPlay** または 正解後: 状態 = Loading → API で 1 問取得 → 取得成功したら `q`, `c`, `a` を保存し、UMG に表示 → 壁を ResetWall → StartMoving → 状態 = Playing。
   - ドアに触れた: 選択 0 or 1 を受け取る → `Choice == AnswerIndex` なら 状態 = Correct、タイマーで 1.5 秒後に「次の問題」へ。  
     `Choice != AnswerIndex` なら 状態 = GameOver。
   - 壁に触れた: 状態 = GameOver。
4. **GameOver 時**: 「GAME OVER」の Text を表示（別 Widget または同じ Widget のパネルを表示）。Phase 1 では「もう一度」は後回しでも可。

---

## Step 9: 壁とゲームモードのつなぎ

1. レベルに配置した `BP_Wall` に、**GameMode や GameState への参照**を持たせるか、**Event Dispatcher** で「ドア 0 に触れた」「ドア 1 に触れた」「壁に触れた」をブロードキャストする。
2. GameMode（または HUD/PlayerController）がそれを購読し、上記の状態遷移と判定を行う。

---

## Step 10: 動作確認

1. クイズ API サーバーを起動（`cd server && python main.py`）。
2. UE で Play。廊下・壁・問題文が表示され、壁が手前に迫る。
3. 左右移動で**左ドア** or **右ドア**に進入 → 正解なら「正解！」→ 次の問題が表示され、壁がリセットして再開。
4. 不正解のドア or 壁に触れる → ゲームオーバー。

---

## トラブルシューティング

- **API に接続できない**: エディタとサーバーが同じ PC なら `127.0.0.1:8000`。パッケージ後は同じ PC でサーバーを立てるか、URL を設定可能にする。
- **コリジョンが反応しない**: 壁・ドアの Collision を **Query and Overlap** にし、プレイヤー側も Overlap で反応する Preset にする。
- **日本語が表示されない**: フォントアセットで日本語を含むフォントを指定する（Phase 3 で調整可）。

---

## 次のステップ

Phase 1 が動いたら、Phase 2 でタイトル・設定・10問チャレンジ・リザルトを追加する。
