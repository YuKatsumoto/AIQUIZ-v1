#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "QuizTypes.h"

class FQuizOfflineBank
{
public:
	bool LoadFromFile(const FString& AbsolutePath);
	TArray<FQuizItem> GetQuizzes(
		const FString& Subject,
		int32 Grade,
		const FString& Difficulty,
		const FString& Mode,
		int32 Count) const;

private:
	TSharedPtr<FJsonObject> Root;
	static bool NormalizeRawToItem(const TSharedPtr<FJsonObject>& Raw, FQuizItem& Out);
	static float ComplexityScore(const FQuizItem& Item, const FString& Subject, int32 Grade);
	static TArray<FQuizItem> BucketByDifficulty(
		TArray<FQuizItem>& Items,
		const FString& Subject,
		int32 Grade,
		const FString& Difficulty);
	static FQuizItem FallbackQuestion(const FString& Subject, int32 Grade);
};
