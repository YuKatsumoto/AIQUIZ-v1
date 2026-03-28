#include "Quiz/QuizPromptBuilder.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

static int32 SafeGrade(int32 G)
{
	return FMath::Clamp(G, 1, 6);
}

static int32 DifficultyIdx(const FString& D)
{
	if (D == TEXT("簡単"))
	{
		return 0;
	}
	if (D == TEXT("難しい"))
	{
		return 2;
	}
	return 1;
}

static FString RecommendedDifficulty(const FString& Subject, int32 Grade)
{
	const int32 G = SafeGrade(Grade);
	if (Subject == TEXT("算数"))
	{
		if (G <= 2)
		{
			return TEXT("簡単");
		}
		if (G <= 4)
		{
			return TEXT("普通");
		}
		return TEXT("難しい");
	}
	if (Subject == TEXT("理科"))
	{
		if (G <= 2)
		{
			return TEXT("簡単");
		}
		if (G <= 4)
		{
			return TEXT("普通");
		}
		return TEXT("難しい");
	}
	if (Subject == TEXT("国語"))
	{
		if (G <= 2)
		{
			return TEXT("簡単");
		}
		if (G <= 5)
		{
			return TEXT("普通");
		}
		return TEXT("難しい");
	}
	if (G <= 2)
	{
		return TEXT("簡単");
	}
	if (G <= 4)
	{
		return TEXT("普通");
	}
	return TEXT("難しい");
}

static FString EffectiveDifficulty(const FString& Subject, int32 Grade, const FString& Requested)
{
	const int32 G = SafeGrade(Grade);
	const int32 ReqIdx = DifficultyIdx(Requested);
	const int32 RecIdx = DifficultyIdx(RecommendedDifficulty(Subject, G));
	const int32 MaxIdx = 2;
	int32 MinAllowed = FMath::Max(0, RecIdx - 1);
	int32 MaxAllowed = FMath::Min(MaxIdx, RecIdx + 1);
	if (G <= 2)
	{
		MaxAllowed = FMath::Min(MaxAllowed, 1);
	}
	else if (G >= 5)
	{
		MinAllowed = FMath::Max(MinAllowed, 1);
	}
	const int32 EffIdx = FMath::Clamp(ReqIdx, MinAllowed, MaxAllowed);
	const TArray<FString> Lv = { TEXT("簡単"), TEXT("普通"), TEXT("難しい") };
	return Lv[EffIdx];
}

static TArray<FString> TopicsFor(const FString& Subject, int32 Grade)
{
	const int32 G = SafeGrade(Grade);
	if (Subject == TEXT("算数"))
	{
		switch (G)
		{
		case 1:
			return { TEXT("足し算"), TEXT("引き算"), TEXT("時計の読み方"), TEXT("図形") };
		case 2:
			return { TEXT("九九"), TEXT("長さの単位(cm, m)"), TEXT("かさ(L, dL)"), TEXT("時刻と時間") };
		case 3:
			return { TEXT("割り算"), TEXT("小数"), TEXT("分数"), TEXT("円と球") };
		case 4:
			return { TEXT("面積"), TEXT("角度"), TEXT("大きな数"), TEXT("小数の計算") };
		case 5:
			return { TEXT("割合"), TEXT("小数の掛け算・割り算"), TEXT("体積"), TEXT("平均") };
		default:
			return { TEXT("比"), TEXT("速さ"), TEXT("比例と反比例"), TEXT("データの活用") };
		}
	}
	if (Subject == TEXT("理科"))
	{
		switch (G)
		{
		case 1:
			return { TEXT("身近な植物"), TEXT("身近な生き物"), TEXT("季節の草花"), TEXT("虫") };
		case 2:
			return { TEXT("野菜の育ち方"), TEXT("天気"), TEXT("季節の生き物"), TEXT("おもちゃの仕組み") };
		case 3:
			return { TEXT("磁石の性質"), TEXT("電気の通り道"), TEXT("昆虫の体のつくり"), TEXT("植物の育ち方") };
		case 4:
			return { TEXT("星と星座"), TEXT("月の動き"), TEXT("空気と水の性質"), TEXT("乾電池と豆電球") };
		case 5:
			return { TEXT("メダカの誕生"), TEXT("植物の発芽と成長"), TEXT("天気の変化"), TEXT("電磁石の性質") };
		default:
			return { TEXT("人体のつくりと働き"), TEXT("光合成"), TEXT("水溶液の性質"), TEXT("地球と環境") };
		}
	}
	switch (G)
	{
	case 1:
		return { TEXT("ひらがな"), TEXT("カタカナ"), TEXT("簡単な漢字"), TEXT("物の名前") };
	case 2:
		return { TEXT("漢字の読み書き"), TEXT("反対の意味の言葉"), TEXT("主語と述語"), TEXT("様子を表す言葉") };
	case 3:
		return { TEXT("ローマ字"), TEXT("ことわざ"), TEXT("部首"), TEXT("修飾語") };
	case 4:
		return { TEXT("慣用句"), TEXT("敬語の基本"), TEXT("つなぎ言葉"), TEXT("熟語の構成") };
	case 5:
		return { TEXT("敬語"), TEXT("四字熟語"), TEXT("同音異義語"), TEXT("古典(竹取物語など)") };
	default:
		return { TEXT("短歌・俳句"), TEXT("歴史的仮名遣い"), TEXT("比喩"), TEXT("言葉の由来") };
	}
}

static void AppendGradeScopeLines(int32 Grade, const FString& Subject, TArray<FString>& Lines)
{
	const int32 G = SafeGrade(Grade);
	const TArray<FString> Allowed = TopicsFor(Subject, G);
	if (Allowed.Num() > 0)
	{
		FString Joined = FString::Join(Allowed, TEXT(", "));
		Lines.Add(FString::Printf(TEXT("IMPORTANT: Allowed curriculum topics for this exact grade: %s."), *Joined));
		Lines.Add(TEXT("IMPORTANT: Every quiz must clearly belong to one of the allowed curriculum topics above."));
	}
	struct FScope
	{
		FString Must;
		FString Avoid;
	};
	static TMap<FString, FScope> MathScopes;
	static bool bMathInit = false;
	if (!bMathInit)
	{
		bMathInit = true;
		MathScopes.Add(TEXT("1_算数"), { TEXT("20までのたし算・ひき算、数の大小、簡単な時計や図形"),
			TEXT("分数・小数・割合・速さ・体積のような上級内容") });
		MathScopes.Add(TEXT("2_算数"), { TEXT("九九、長さ・かさ、時刻、簡単な表の読み取り"), TEXT("割合・速さ・体積・比のような高学年中心の内容") });
		MathScopes.Add(TEXT("3_算数"), { TEXT("かけ算、わり算、分数の入口、円と球、長さ・重さ"), TEXT("割合・比・複雑な速さや高難度の面積問題") });
		MathScopes.Add(TEXT("4_算数"), { TEXT("大きな数、面積、角、折れ線グラフ、小数・分数"), TEXT("比や高度な割合など高学年中心の内容") });
		MathScopes.Add(TEXT("5_算数"), { TEXT("小数と分数の計算、割合、平均、体積、図形の性質"), TEXT("中学レベルの方程式や座標") });
		MathScopes.Add(TEXT("6_算数"), { TEXT("比、割合、速さ、円の面積、資料の見方、複数段階の判断"), TEXT("低学年向けの一桁計算や単純な個数計算だけの問題") });
	}
	auto Key = FString::Printf(TEXT("%d_%s"), G, *Subject);
	FString Must, Avoid;
	if (Subject == TEXT("算数"))
	{
		if (const FScope* S = MathScopes.Find(FString::Printf(TEXT("%d_算数"), G)))
		{
			Must = S->Must;
			Avoid = S->Avoid;
		}
	}
	else if (Subject == TEXT("理科"))
	{
		static TMap<int32, FScope> Sci = { { 3, { TEXT("植物や昆虫、光、音、磁石、電気など身近な観察内容"), TEXT("人体のしくみや水溶液など高学年中心の内容") } },
			{ 4, { TEXT("電流、天気、月や星、温度、金属や空気と水の変化"), TEXT("消化や血液循環、地層など6年寄りの内容") } },
			{ 5, { TEXT("発芽と成長、流れる水、天気、ふりこ、てこ、電磁石"), TEXT("中学理科レベルの化学式や専門用語") } },
			{ 6, { TEXT("人体、水溶液、月と太陽、土地のつくり、発電や電気の利用"), TEXT("中学以降の専門計算や抽象理論") } } };
		if (const FScope* S = Sci.Find(G))
		{
			Must = S->Must;
			Avoid = S->Avoid;
		}
	}
	else
	{
		static TMap<int32, FScope> Jap = { { 1, { TEXT("ひらがな、かたかな、やさしい言葉、短い文の読解"), TEXT("敬語や抽象的な文法用語") } },
			{ 2, { TEXT("語彙、短文読解、主語と述語の入口、漢字の基本"), TEXT("高度な敬語や長文要旨問題") } },
			{ 3, { TEXT("漢字、ことわざ・慣用句の入口、段落の読み取り"), TEXT("難しい敬語運用や抽象的な評論読解") } },
			{ 4, { TEXT("文法の基本、漢字、要点把握、段落や接続の理解"), TEXT("中学寄りの古典文法や難解な評論") } },
			{ 5, { TEXT("敬語、文の組み立て、熟語、資料や文章の読み取り"), TEXT("低学年向けの単純な語句暗記だけの問題") } },
			{ 6, { TEXT("敬語、表現の効果、文章構成、要旨把握、漢字や語句の使い分け"), TEXT("低学年向けの単純な読みだけの問題") } } };
		if (const FScope* S = Jap.Find(G))
		{
			Must = S->Must;
			Avoid = S->Avoid;
		}
	}
	if (!Must.IsEmpty())
	{
		Lines.Add(FString::Printf(TEXT("IMPORTANT: Target this grade feel: %s."), *Must));
	}
	if (!Avoid.IsEmpty())
	{
		Lines.Add(FString::Printf(TEXT("IMPORTANT: Avoid level mismatch such as: %s."), *Avoid));
	}
	if (Subject == TEXT("算数") && G >= 5)
	{
		Lines.Add(TEXT("IMPORTANT: For upper-elementary math, avoid low-grade one-step word problems unless the question also requires ratio, percentage, speed, area, volume, graph reading, or multi-step reasoning."));
	}
	if (Subject == TEXT("国語") && G >= 5)
	{
		Lines.Add(TEXT("IMPORTANT: For grade 5-6 Japanese, prefer passage interpretation, grammar, kanji usage, 敬語, or reasoning about wording over very short single-word meaning drills."));
	}
	if (Subject == TEXT("理科") && G >= 5)
	{
		Lines.Add(TEXT("IMPORTANT: For grade 5-6 science, prefer observation, experiment, comparison, explanation of cause/effect, or curriculum concepts over simple fact recall only."));
	}
}

static void AppendGradeFitLines(int32 Grade, const FString& Subject, const FString& EffDiff, TArray<FString>& Lines)
{
	const int32 Idx = DifficultyIdx(EffDiff);
	Lines.Add(TEXT("IMPORTANT: Match the requested grade and subject exactly. Do not downgrade to lower-grade content."));
	Lines.Add(TEXT("IMPORTANT: Use age-appropriate terms, units, and curriculum-style phrasing for the specified grade."));
	if (Idx == 1)
	{
		Lines.Add(TEXT("For NORMAL difficulty, generate textbook-middle level questions for that grade (not introductory or review-only lower-grade questions)."));
		Lines.Add(TEXT("For NORMAL difficulty, include at least one reasoning step (comparison, interpretation, calculation, or cause/effect), not pure recall only."));
		Lines.Add(TEXT("Make wrong choices plausible for students of that grade and subject."));
		if (Grade >= 3)
		{
			Lines.Add(TEXT("If grade >= 3, avoid overly easy lower-grade items such as obvious single-step one-digit arithmetic or simple word guessing."));
		}
		if (Grade >= 5)
		{
			Lines.Add(TEXT("If grade >= 5, prefer questions requiring organizing information, intermediate steps, or checking evidence/reasoning."));
		}
	}
	else if (Idx == 2)
	{
		Lines.Add(TEXT("For HARD difficulty, stay within grade scope but use application-oriented or multi-step questions."));
		Lines.Add(TEXT("Combine multiple learned points from the same grade when possible."));
	}
	else
	{
		Lines.Add(TEXT("For EASY difficulty, keep it basic but still within the specified grade and subject scope."));
	}
}

FString FQuizPromptBuilder::BuildOnlinePrompt(
	const FString& Subject,
	int32 Grade,
	const FString& Difficulty,
	int32 Count,
	const TArray<FString>& History,
	const TArray<TSharedPtr<FJsonObject>>& GoodExamples,
	const TArray<TSharedPtr<FJsonObject>>& BadExamples)
{
	const int32 G = SafeGrade(Grade);
	const FString EffDiff = EffectiveDifficulty(Subject, G, Difficulty);
	const TArray<FString> Topics = TopicsFor(Subject, G);
	const FString Topic = Topics[FMath::RandRange(0, FMath::Max(0, Topics.Num() - 1))];
	TArray<FString> TopicBatch = Topics;
	const int32 MaxPick = FMath::Clamp(Count, 2, 6);
	while (TopicBatch.Num() > MaxPick)
	{
		TopicBatch.RemoveAt(FMath::RandRange(0, TopicBatch.Num() - 1));
	}
	FString ExampleJson = TEXT("[{\"q\":\"問題文1\",\"c\":[\"選択肢A\",\"選択肢B\"],\"a\":0,\"e\":\"解説1\"},{\"q\":\"問題文2\",\"c\":[\"選択肢C\",\"選択肢D\"],\"a\":1,\"e\":\"解説2\"}]");
	FString DiffInstr;
	if (EffDiff == TEXT("簡単"))
	{
		DiffInstr = TEXT("・基礎的な知識を問う問題にしてください。\n・ひねりは加えず、ストレートな問題にしてください。");
	}
	else if (EffDiff == TEXT("難しい"))
	{
		DiffInstr = TEXT("・応用力や思考力を問う少し難しい問題にしてください。\n・引っかけ問題や、複数のステップを要する問題を含めても構いません。");
	}
	else
	{
		DiffInstr = TEXT("・標準的なレベルの問題にしてください。\n・教科書の練習問題レベルを意識してください。");
	}
	TArray<FString> Lines;
	Lines.Add(FString::Printf(TEXT("日本の小学校%d年生向け、%sの『%s』に関する二択クイズを作成してください。"), G, *Subject, *Topic));
	Lines.Add(FString::Printf(TEXT("難易度設定: %s"), *EffDiff));
	Lines.Add(DiffInstr);
	if (G <= 2)
	{
		Lines.Insert(TEXT("特別ルール: 小学1・2年生向けなので、漢字は使わず「ひらがな」を多くしてください。"), 3);
		Lines.Insert(TEXT("特別ルール: 難しい言葉は使わず、子供がわかるやさしい言葉で書いてください。"), 4);
	}
	Lines.Add(TEXT("ルール1: 問題文に絵文字や記号を入れないこと"));
	Lines.Add(TEXT("ルール2: JSONの配列(List)形式のみ出力してください。選択肢は2つ。子供向けの言葉で。"));
	Lines.Add(FString::Printf(TEXT("例: %s"), *ExampleJson));
	Lines.Add(FString::Printf(TEXT("IMPORTANT: Return exactly %d quiz objects in one JSON array."), FMath::Max(1, Count)));
	Lines.Add(TEXT("IMPORTANT: Output JSON only, with no markdown and no extra prose."));
	Lines.Add(TEXT("IMPORTANT: Within one response, diversify sub-topics and avoid repeating the same unit-conversion pattern/template."));
	Lines.Add(FString::Printf(TEXT("IMPORTANT: Candidate topics for this batch are: %s."), *FString::Join(TopicBatch, TEXT(", "))));
	Lines.Add(TEXT("IMPORTANT: Spread the quizzes across different candidate topics when possible."));
	if (Subject == TEXT("国語") && G >= 5)
	{
		Lines.Add(TEXT("IMPORTANT (Japanese grade 5-6): Avoid generating consecutive vocabulary-meaning items."));
		Lines.Add(TEXT("When outputting multiple quizzes, each quiz must use a different sub-genre (reading comprehension, grammar, kanji/notation, vocabulary usage, honorific/polite forms)."));
		Lines.Add(TEXT("Do not output two questions in the same 'word meaning / phrase meaning' format in one response."));
	}
	AppendGradeScopeLines(G, Subject, Lines);
	AppendGradeFitLines(G, Subject, EffDiff, Lines);
	TArray<TSharedPtr<FJsonObject>> ScopedGood;
	for (const TSharedPtr<FJsonObject>& E : GoodExamples)
	{
		if (!E.IsValid())
		{
			continue;
		}
		if (E->GetStringField(TEXT("subject")) == Subject && E->GetStringField(TEXT("grade")) == FString::FromInt(G))
		{
			ScopedGood.Add(E);
		}
	}
	if (ScopedGood.Num() > 0)
	{
		const TSharedPtr<FJsonObject>& Sample = ScopedGood[FMath::RandRange(0, ScopedGood.Num() - 1)];
		const FString Qtxt = Sample->GetStringField(TEXT("q")).TrimStartAndEnd();
		if (!Qtxt.IsEmpty())
		{
			Lines.Add(FString::Printf(TEXT("※参考: 過去に高く評価された良問のテイストや難易度を参考にしてください -> Q:%s"), *Qtxt));
		}
	}
	if (History.Num() > 0)
	{
		Lines.Add(TEXT("※以下の問題とは内容・数値を必ず変えて作成してください:"));
		const int32 Start = FMath::Max(0, History.Num() - 20);
		for (int32 i = Start; i < History.Num(); ++i)
		{
			const FString H = History[i].TrimStartAndEnd();
			if (!H.IsEmpty())
			{
				Lines.Add(FString::Printf(TEXT("- %s"), *H));
			}
		}
	}
	TArray<TSharedPtr<FJsonObject>> BadPool;
	for (const TSharedPtr<FJsonObject>& B : BadExamples)
	{
		if (!B.IsValid() || B->GetStringField(TEXT("q")).IsEmpty())
		{
			continue;
		}
		const FString BS = B->GetStringField(TEXT("subject")).TrimStartAndEnd();
		const FString BG = B->GetStringField(TEXT("grade")).TrimStartAndEnd();
		if ((BS == Subject && BG == FString::FromInt(G)) || (BS.IsEmpty() && BG.IsEmpty()))
		{
			BadPool.Add(B);
		}
	}
	if (BadPool.Num() == 0)
	{
		for (const TSharedPtr<FJsonObject>& B : BadExamples)
		{
			if (B.IsValid() && !B->GetStringField(TEXT("q")).IsEmpty())
			{
				BadPool.Add(B);
			}
		}
	}
	if (BadPool.Num() > 0)
	{
		Lines.Add(TEXT("※以下の問題は以前「悪い」と評価されたので、似た形式や内容の問題は絶対に出題しないでください:"));
		const int32 N = FMath::Min(3, BadPool.Num());
		for (int32 k = 0; k < N; ++k)
		{
			const int32 Idx = FMath::RandRange(0, BadPool.Num() - 1);
			Lines.Add(FString::Printf(TEXT("- %s"), *BadPool[Idx]->GetStringField(TEXT("q")).TrimStartAndEnd()));
		}
	}
	FString Out;
	for (const FString& Ln : Lines)
	{
		if (!Ln.TrimStartAndEnd().IsEmpty())
		{
			if (!Out.IsEmpty())
			{
				Out += TEXT("\n");
			}
			Out += Ln;
		}
	}
	return Out;
}
