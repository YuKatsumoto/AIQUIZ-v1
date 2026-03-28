#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "QuizTypes.h"

struct FQuizJsonUtils
{
	static bool TryParseQuizObject(const TSharedPtr<FJsonObject>& Obj, FQuizItem& Out, const FString& SrcLabel);
	static TArray<FQuizItem> ExtractQuizzesFromText(const FString& RawText);
	static TArray<TSharedPtr<FJsonValue>> ExtractJsonArrayFromText(const FString& RawText);
};
