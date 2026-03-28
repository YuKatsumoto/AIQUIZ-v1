#include "Quiz/QuizOfflineBank.h"
#include "Quiz/QuizConstants.h"
#include "Dom/JsonValue.h"
#include "HAL/PlatformFilemanager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Internationalization/Regex.h"

bool FQuizOfflineBank::LoadFromFile(const FString& AbsolutePath)
{
	FString JsonStr;
	if (!FFileHelper::LoadFileToString(JsonStr, *AbsolutePath))
	{
		return false;
	}
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
	TSharedPtr<FJsonValue> RootVal;
	if (!FJsonSerializer::Deserialize(Reader, RootVal) || !RootVal.IsValid() || RootVal->Type != EJson::Object)
	{
		return false;
	}
	Root = RootVal->AsObject();
	return Root.IsValid();
}

bool FQuizOfflineBank::NormalizeRawToItem(const TSharedPtr<FJsonObject>& Raw, FQuizItem& Out)
{
	if (!Raw.IsValid())
	{
		return false;
	}
	FString Q = Raw->GetStringField(TEXT("q")).TrimStartAndEnd();
	const TArray<TSharedPtr<FJsonValue>>* CArr = nullptr;
	if (!Raw->TryGetArrayField(TEXT("c"), CArr) || !CArr || CArr->Num() != 2)
	{
		return false;
	}
	FString C0, C1;
	if (!(*CArr)[0]->TryGetString(C0) || !(*CArr)[1]->TryGetString(C1))
	{
		return false;
	}
	C0.TrimStartAndEndInline();
	C1.TrimStartAndEndInline();
	double ADbl = 0;
	if (!Raw->TryGetNumberField(TEXT("a"), ADbl))
	{
		return false;
	}
	const int32 A = FMath::RoundToInt(ADbl);
	if ((A != 0 && A != 1) || Q.IsEmpty() || C0.IsEmpty() || C1.IsEmpty())
	{
		return false;
	}
	FString E = Raw->GetStringField(TEXT("e"));
	if (E.IsEmpty())
	{
		E = Raw->GetStringField(TEXT("exp"));
	}
	E.TrimStartAndEndInline();
	FString Src = Raw->GetStringField(TEXT("src"));
	if (Src.IsEmpty())
	{
		Src = TEXT("OFFLINE");
	}
	Out.Question = Q;
	Out.Choice0 = C0;
	Out.Choice1 = C1;
	Out.AnswerIndex = A;
	Out.Explanation = E;
	Out.Source = Src;
	return true;
}

float FQuizOfflineBank::ComplexityScore(const FQuizItem& Item, const FString& Subject, int32 Grade)
{
	const FString Text = Item.Question + TEXT(" ") + Item.Choice0 + TEXT(" ") + Item.Choice1 + TEXT(" ") + Item.Explanation;
	const FString QText = Item.Question;
	float Score = 0.f;
	Score += QText.Len() / 40.f;
	Score += Item.Explanation.Len() / 80.f;
	static const FRegexPattern DigitPat(TEXT("[0-9]"));
	FRegexMatcher MD(DigitPat, Text);
	while (MD.FindNext())
	{
		Score += 0.08f;
	}
	static const FRegexPattern MathSym(TEXT("[+\\-*/÷×%]"));
	FRegexMatcher MM(MathSym, Text);
	while (MM.FindNext())
	{
		Score += 0.25f;
	}
	static const FRegexPattern ParenPat(TEXT("[()（）]"));
	FRegexMatcher MP(ParenPat, Text);
	while (MP.FindNext())
	{
		Score += 0.2f;
	}
	if (QText.Contains(TEXT("【応用】")))
	{
		Score += 1.2f;
	}
	if (QText.Contains(TEXT("【基本】")))
	{
		Score -= 0.6f;
	}
	if (Subject == TEXT("算数"))
	{
		const TArray<FString> Tok = { TEXT("割合"), TEXT("比"), TEXT("速さ"), TEXT("体積"), TEXT("平均"), TEXT("合同"), TEXT("比例"), TEXT("反比例") };
		for (const FString& T : Tok)
		{
			if (Text.Contains(T))
			{
				Score += 0.9f;
			}
		}
		static const FRegexPattern ThreeD(TEXT("[0-9]{3,}"));
		FRegexMatcher M3(ThreeD, Text);
		if (M3.FindNext())
		{
			Score += 0.4f;
		}
	}
	else if (Subject == TEXT("理科"))
	{
		const TArray<FString> Tok = { TEXT("実験"), TEXT("観察"), TEXT("原因"), TEXT("結果"), TEXT("規則"), TEXT("電磁石"), TEXT("水溶液"), TEXT("燃焼"), TEXT("光合成") };
		for (const FString& T : Tok)
		{
			if (Text.Contains(T))
			{
				Score += 0.7f;
			}
		}
	}
	else if (Subject == TEXT("国語"))
	{
		const TArray<FString> Tok = { TEXT("敬語"), TEXT("四字熟語"), TEXT("古典"), TEXT("短歌"), TEXT("俳句"), TEXT("歴史的仮名遣い"), TEXT("比喩") };
		for (const FString& T : Tok)
		{
			if (Text.Contains(T))
			{
				Score += 0.9f;
			}
		}
	}
	Score -= FMath::Max(0, Grade - 1) * 0.08f;
	return Score;
}

TArray<FQuizItem> FQuizOfflineBank::BucketByDifficulty(
	TArray<FQuizItem>& Items,
	const FString& Subject,
	int32 Grade,
	const FString& Difficulty)
{
	if (Items.Num() <= 2)
	{
		return Items;
	}
	Items.Sort([&](const FQuizItem& A, const FQuizItem& B) {
		return ComplexityScore(A, Subject, Grade) < ComplexityScore(B, Subject, Grade);
	});
	const int32 N = Items.Num();
	const int32 LowEnd = FMath::Max(1, N / 3);
	const int32 HighStart = FMath::Max(LowEnd, (2 * N) / 3);
	TArray<FQuizItem> Slice;
	if (Difficulty == TEXT("簡単"))
	{
		Slice.Append(Items.GetData(), LowEnd);
	}
	else if (Difficulty == TEXT("難しい"))
	{
		Slice.Append(Items.GetData() + HighStart, N - HighStart);
	}
	else
	{
		Slice.Append(Items.GetData() + LowEnd, HighStart - LowEnd);
	}
	return Slice.Num() > 0 ? Slice : Items;
}

FQuizItem FQuizOfflineBank::FallbackQuestion(const FString& Subject, int32 Grade)
{
	const int32 A = FMath::RandRange(2, 20);
	const int32 B = FMath::RandRange(1, 10);
	const int32 Ans = A + B;
	int32 Wrong = Ans + (FMath::RandBool() ? 1 : -1) * FMath::RandRange(1, 2);
	const FString SAns = FString::FromInt(Ans);
	const FString SWrong = FString::FromInt(Wrong);
	TArray<FString> C = { SAns, SWrong };
	if (FMath::RandBool())
	{
		C.Swap(0, 1);
	}
	FQuizItem Q;
	Q.Question = FString::Printf(TEXT("[%s%d年] %d+%d はどちら？"), *Subject, Grade, A, B);
	Q.Choice0 = C[0];
	Q.Choice1 = C[1];
	Q.AnswerIndex = (C[0] == SAns) ? 0 : 1;
	Q.Explanation = FString::Printf(TEXT("%d+%d=%d"), A, B, Ans);
	Q.Source = TEXT("FALLBACK");
	return Q;
}

TArray<FQuizItem> FQuizOfflineBank::GetQuizzes(
	const FString& Subject,
	int32 Grade,
	const FString& Difficulty,
	const FString& Mode,
	int32 Count) const
{
	TArray<FQuizItem> Items;
	if (!Root.IsValid())
	{
		if (Mode == QuizConst::ModeTen)
		{
			for (int32 i = 0; i < FMath::Max(1, Count); ++i)
			{
				Items.Add(FallbackQuestion(Subject, Grade));
			}
		}
		else
		{
			Items.Add(FallbackQuestion(Subject, Grade));
		}
		return Items;
	}
	const TSharedPtr<FJsonObject>* SubObj = nullptr;
	if (!Root->TryGetObjectField(Subject, SubObj) || !SubObj->IsValid())
	{
		if (Mode == QuizConst::ModeTen)
		{
			for (int32 i = 0; i < FMath::Max(1, Count); ++i)
			{
				Items.Add(FallbackQuestion(Subject, Grade));
			}
		}
		else
		{
			Items.Add(FallbackQuestion(Subject, Grade));
		}
		return Items;
	}
	const FString GradeKey = FString::FromInt(Grade);
	const TArray<TSharedPtr<FJsonValue>>* RawArr = nullptr;
	if (!(*SubObj)->TryGetArrayField(GradeKey, RawArr) || !RawArr)
	{
		if (Mode == QuizConst::ModeTen)
		{
			for (int32 i = 0; i < FMath::Max(1, Count); ++i)
			{
				Items.Add(FallbackQuestion(Subject, Grade));
			}
		}
		else
		{
			Items.Add(FallbackQuestion(Subject, Grade));
		}
		return Items;
	}
	for (const TSharedPtr<FJsonValue>& V : *RawArr)
	{
		if (!V.IsValid() || V->Type != EJson::Object)
		{
			continue;
		}
		FQuizItem It;
		if (NormalizeRawToItem(V->AsObject(), It))
		{
			Items.Add(It);
		}
	}
	if (Items.Num() == 0)
	{
		if (Mode == QuizConst::ModeTen)
		{
			TArray<FQuizItem> Out;
			for (int32 i = 0; i < FMath::Max(1, Count); ++i)
			{
				Out.Add(FallbackQuestion(Subject, Grade));
			}
			return Out;
		}
		return { FallbackQuestion(Subject, Grade) };
	}
	TArray<FQuizItem> Pool = Items;
	Pool = BucketByDifficulty(Pool, Subject, Grade, Difficulty);
	for (int32 i = 0; i < Pool.Num(); ++i)
	{
		const int32 J = FMath::RandRange(i, Pool.Num() - 1);
		Pool.Swap(i, J);
	}
	if (Mode == QuizConst::ModeTen)
	{
		TArray<FQuizItem> Uniq;
		TSet<FString> Seen;
		for (const FQuizItem& Q : Pool)
		{
			if (Seen.Contains(Q.Question))
			{
				continue;
			}
			Seen.Add(Q.Question);
			Uniq.Add(Q);
			if (Uniq.Num() >= Count)
			{
				break;
			}
		}
		for (const FQuizItem& Q : Items)
		{
			if (Uniq.Num() >= Count)
			{
				break;
			}
			if (Seen.Contains(Q.Question))
			{
				continue;
			}
			Seen.Add(Q.Question);
			Uniq.Add(Q);
		}
		while (Uniq.Num() < Count)
		{
			Uniq.Add(FallbackQuestion(Subject, Grade));
		}
		return Uniq;
	}
	return { Pool[FMath::RandRange(0, Pool.Num() - 1)] };
}
