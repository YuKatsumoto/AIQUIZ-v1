#include "Quiz/QuizValidation.h"
#include "Internationalization/Regex.h"

static float MathGradeFitScore(const FString& Text, int32 Grade)
{
	float Score = 0.55f;
	static const FRegexPattern DigitPat(TEXT("[0-9]"));
	int32 NumCount = 0;
	FRegexMatcher M(DigitPat, Text);
	while (M.FindNext())
	{
		++NumCount;
	}
	Score += FMath::Min(0.25f, NumCount * 0.02f);
	if (Grade >= 5 && (Text.Contains(TEXT("割合")) || Text.Contains(TEXT("速さ")) || Text.Contains(TEXT("体積")) || Text.Contains(TEXT("比"))))
	{
		Score += 0.2f;
	}
	if (Grade <= 2)
	{
		static const FRegexPattern ThreeDigits(TEXT("[0-9]{3,}"));
		FRegexMatcher M2(ThreeDigits, Text);
		if (M2.FindNext())
		{
			Score -= 0.25f;
		}
	}
	return FMath::Clamp(Score, 0.f, 1.f);
}

static float ScienceGradeFitScore(const FString& Text, int32 Grade)
{
	float Score = 0.55f;
	if (Text.Contains(TEXT("実験")) || Text.Contains(TEXT("観察")) || Text.Contains(TEXT("原因")) || Text.Contains(TEXT("結果")))
	{
		Score += 0.15f;
	}
	if (Grade >= 5
		&& (Text.Contains(TEXT("電磁石")) || Text.Contains(TEXT("水溶液")) || Text.Contains(TEXT("燃焼")) || Text.Contains(TEXT("光合成"))))
	{
		Score += 0.2f;
	}
	return FMath::Clamp(Score, 0.f, 1.f);
}

static float JapaneseGradeFitScore(const FString& Text, int32 Grade)
{
	float Score = 0.55f;
	if (Text.Contains(TEXT("語句")) || Text.Contains(TEXT("文法")) || Text.Contains(TEXT("敬語")))
	{
		Score += 0.12f;
	}
	if (Grade >= 5
		&& (Text.Contains(TEXT("四字熟語")) || Text.Contains(TEXT("古典")) || Text.Contains(TEXT("比喩")) || Text.Contains(TEXT("短歌"))
			|| Text.Contains(TEXT("俳句"))))
	{
		Score += 0.2f;
	}
	return FMath::Clamp(Score, 0.f, 1.f);
}

static int32 DifficultyIndex(const FString& D)
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

FString FQuizValidation::GradeFitRejectReason(
	const FQuizItem& Quiz,
	const FString& Subject,
	int32 Grade,
	const FString& Difficulty,
	float ThresholdRelax)
{
	const FString Text = Quiz.Question + TEXT(" ") + Quiz.Choice0 + TEXT(" ") + Quiz.Choice1 + TEXT(" ") + Quiz.Explanation;
	float Score = 0.55f;
	if (Subject == TEXT("算数"))
	{
		Score = MathGradeFitScore(Text, Grade);
	}
	else if (Subject == TEXT("理科"))
	{
		Score = ScienceGradeFitScore(Text, Grade);
	}
	else
	{
		Score = JapaneseGradeFitScore(Text, Grade);
	}
	float Base = 0.52f;
	if (Difficulty == TEXT("簡単"))
	{
		Base -= 0.05f;
	}
	else if (Difficulty == TEXT("難しい"))
	{
		Base += 0.05f;
	}
	const float Threshold = FMath::Max(0.28f, Base - ThresholdRelax);
	if (Score < Threshold)
	{
		return FString::Printf(TEXT("grade_fit_low:%f<%f"), Score, Threshold);
	}
	if (Grade <= 2 && (Text.Contains(TEXT("方程式")) || Text.Contains(TEXT("一次関数")) || Text.Contains(TEXT("二次方程式"))))
	{
		return TEXT("topic_too_advanced_low_grade");
	}
	if (Grade >= 5 && (Text.Contains(TEXT("ひらがな")) || Text.Contains(TEXT("カタカナ"))))
	{
		return TEXT("topic_too_easy_upper_grade");
	}
	return FString();
}

static FString NormalizeQ(const FString& Q)
{
	FString S = Q;
	S.ReplaceInline(TEXT(" "), TEXT(""));
	S.ReplaceInline(TEXT("\t"), TEXT(""));
	S.ReplaceInline(TEXT("\n"), TEXT(""));
	return S.ToLower();
}

static FString QuestionPatternKey(const FString& Q)
{
	FString S = NormalizeQ(Q);
	static const FRegexPattern NumPat(TEXT("[0-9]+"));
	FRegexMatcher M(NumPat, S);
	int32 LastStart = 0;
	FString Out;
	while (M.FindNext())
	{
		Out += S.Mid(LastStart, M.GetMatchBeginning() - LastStart);
		Out += TEXT("#");
		LastStart = M.GetMatchEnding();
	}
	Out += S.Mid(LastStart);
	Out.ReplaceInline(TEXT("、"), TEXT(""));
	Out.ReplaceInline(TEXT("。"), TEXT(""));
	Out.ReplaceInline(TEXT(","), TEXT(""));
	Out.ReplaceInline(TEXT("."), TEXT(""));
	Out.ReplaceInline(TEXT("!"), TEXT(""));
	Out.ReplaceInline(TEXT("?"), TEXT(""));
	Out.ReplaceInline(TEXT("！"), TEXT(""));
	Out.ReplaceInline(TEXT("？"), TEXT(""));
	return Out;
}

static TSet<FString> CharBigramSet(const FString& S)
{
	TSet<FString> Set;
	if (S.Len() < 2)
	{
		if (!S.IsEmpty())
		{
			Set.Add(S);
		}
		return Set;
	}
	for (int32 i = 0; i < S.Len() - 1; ++i)
	{
		Set.Add(S.Mid(i, 2));
	}
	return Set;
}

bool FQuizValidation::IsSimilarQuestion(const FQuizItem& Quiz, const TArray<FString>& RecentQuestions)
{
	const FString QNorm = NormalizeQ(Quiz.Question);
	const FString QPat = QuestionPatternKey(Quiz.Question);
	const TSet<FString> QBi = CharBigramSet(QPat);
	for (const FString& R : RecentQuestions)
	{
		const FString Q2 = NormalizeQ(R);
		const FString Q2Pat = QuestionPatternKey(R);
		if (QNorm == Q2)
		{
			return true;
		}
		if (!QPat.IsEmpty() && !Q2Pat.IsEmpty() && QPat == Q2Pat)
		{
			return true;
		}
		if (!QNorm.IsEmpty() && !Q2.IsEmpty() && (Q2.Contains(QNorm) || QNorm.Contains(Q2)))
		{
			return true;
		}
		const TSet<FString> Q2Bi = CharBigramSet(Q2Pat);
		if (QBi.Num() > 0 && Q2Bi.Num() > 0)
		{
			int32 Inter = 0;
			for (const FString& X : QBi)
			{
				if (Q2Bi.Contains(X))
				{
					++Inter;
				}
			}
			TSet<FString> Uni = QBi;
			Uni.Append(Q2Bi);
			const int32 UniNum = Uni.Num();
			if (UniNum > 0 && static_cast<float>(Inter) / static_cast<float>(UniNum) >= 0.84f)
			{
				return true;
			}
		}
	}
	return false;
}

bool FQuizValidation::IsBadRatedQuestion(
	const FRatingsBuckets& Ratings,
	const FQuizItem& Quiz,
	const FString& Subject,
	int32 Grade)
{
	const FString QQ = Quiz.Question.TrimStartAndEnd();
	for (const TSharedPtr<FJsonObject>& Item : Ratings.Bad)
	{
		if (!Item.IsValid())
		{
			continue;
		}
		if (Item->GetStringField(TEXT("q")).TrimStartAndEnd() != QQ)
		{
			continue;
		}
		const FString ItemSubject = Item->GetStringField(TEXT("subject")).TrimStartAndEnd();
		if (!ItemSubject.IsEmpty() && ItemSubject != Subject)
		{
			continue;
		}
		FString GradeStr;
		if (Item->TryGetStringField(TEXT("grade"), GradeStr))
		{
			GradeStr.TrimStartAndEndInline();
			if (!GradeStr.IsEmpty() && GradeStr != FString::FromInt(Grade))
			{
				continue;
			}
		}
		return true;
	}
	return false;
}
