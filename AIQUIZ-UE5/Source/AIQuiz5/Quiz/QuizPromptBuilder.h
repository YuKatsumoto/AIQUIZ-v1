#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

struct FQuizPromptBuilder
{
	static FString BuildOnlinePrompt(
		const FString& Subject,
		int32 Grade,
		const FString& Difficulty,
		int32 Count,
		const TArray<FString>& History,
		const TArray<TSharedPtr<FJsonObject>>& GoodExamples,
		const TArray<TSharedPtr<FJsonObject>>& BadExamples);
};
