# Unreal Engine 用 クイズ API クライアント（Phase 1）

Phase 1 で UE からクイズ API を呼ぶための C++ コードです。**既存の UE5 C++ プロジェクトにコピーして使います。**

## 前提

- Unreal Engine 5（5.4 など）で **C++ プロジェクト**を新規作成していること。プロジェクト名は例: **AIQuizUE**。
- クイズ API サーバー（Phase 0）が `http://127.0.0.1:8000` で起動していること。

## 追加手順

### 1. ファイルをコピーする

このフォルダの次のファイルを、あなたの **UE プロジェクトの `Source/AIQuizUE/`** にコピーします。

- `Source/AIQuizUE/Public/QuizTypes.h` → あなたの `Source/AIQuizUE/Public/`
- `Source/AIQuizUE/Public/QuizApiSubsystem.h` → あなたの `Source/AIQuizUE/Public/`
- `Source/AIQuizUE/Private/QuizApiSubsystem.cpp` → あなたの `Source/AIQuizUE/Private/`

※ プロジェクト名が AIQuizUE でない場合は、フォルダ名をあなたのプロジェクト名に読み替えてください。

### 2. ビルド設定にモジュールを追加する

あなたの `Source/AIQuizUE/AIQuizUE.Build.cs` を開き、**PublicDependencyModuleNames** に次の 3 つを追加します。

- `"HTTP"`
- `"Json"`
- `"JsonUtilities"`

例（追加後）:

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core",
    "CoreUObject",
    "Engine",
    "HTTP",
    "Json",
    "JsonUtilities"
});
```

### 3. プロジェクトをビルドする

- エディタを閉じ、**.uproject を右クリック → Generate Visual Studio project files**。
- ソリューションを開いてビルドするか、エディタから「Live Coding」でビルド。

## Blueprint での使い方

1. **GameInstance** を Blueprint で拡張（例: `BP_QuizGameInstance`）しても、そのまま使えます。  
   （QuizApiSubsystem は GameInstance の Subsystem なので、デフォルトの GameInstance でも利用可能です。）

2. **Quiz Api Subsystem を取得**  
   - 例: Event BeginPlay（PlayerController や GameMode など）で  
     **Get Game Instance** → **Get Subsystem**（Class に `QuizApiSubsystem` を指定）。

3. **Request Quiz を呼ぶ**  
   - **Request Quiz** ノード: Subject に `"算数"`、Grade に `3` などを指定。

4. **結果を受け取る**  
   - **On Quiz Received** に Bind（または Custom Event を割り当て）。  
     引数 **Quiz** が `FQuizItem`（Question, Choices[0], Choices[1], AnswerIndex, Explanation）。
   - **On Quiz Request Failed** に Bind。失敗時（ネットワークエラーなど）の処理。

5. **表示**  
   - Quiz の **Question** を問題文の Text に、**Choices[0]** を左、**Choices[1]** を右の選択肢に表示。  
   - **AnswerIndex** はプレイヤーには見せず、ドアに触れたときの選択 (0 or 1) と比較して正解判定。

## API の URL を変える

`UQuizApiSubsystem` の **Api Base Url** は、Blueprint で Subsystem を取得したあと **Set Api Base Url** で変更できます。  
パッケージ後に別のサーバーを使う場合は、ゲーム開始時に設定するか、DefaultEngine.ini で読み込むように拡張してください。

## トラブルシューティング

- **ビルドエラー「HTTP not found」**  
  → .Build.cs に `"HTTP"` を追加したか確認。追加後は「Generate Visual Studio project files」をやり直す。
- **On Quiz Request Failed ばかり**  
  → サーバーが起動しているか、URL が `http://127.0.0.1:8000` で正しいか確認。  
  → レスポンスが JSON の配列 `[{ "q", "c", "a", ... }]` になっているか（Phase 0 の API 仕様どおりか）確認。
