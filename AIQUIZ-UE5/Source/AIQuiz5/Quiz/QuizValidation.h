#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "QuizTypes.h"

struct FRatingsBuckets
{
	TArray<TSharedPtr<FJsonObject>> Good;
	TArray<TSharedPtr<FJsonObject>> Bad;
};

struct FQuizValidation
{
	static FString GradeFitRejectReason(
		const FQuizItem& Quiz,
		const FString& Subject,
		int32 Grade,
		const FString& Difficulty,
		float ThresholdRelax);

	static bool IsSimilarQuestion(const FQuizItem& Quiz, const TArray<FString>& RecentQuestions);
	static bool IsBadRatedQuestion(const FRatingsBuckets& Ratings, const FQuizItem& Quiz, const FString& Subject, int32 Grade);
};
