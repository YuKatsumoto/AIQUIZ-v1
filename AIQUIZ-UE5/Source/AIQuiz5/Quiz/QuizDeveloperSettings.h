#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "QuizDeveloperSettings.generated.h"

UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "AI Quiz / LLM"))
class UQuizDeveloperSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UQuizDeveloperSettings();

	UPROPERTY(Config, EditAnywhere, Category = "OpenAI", meta = (PasswordField = true))
	FString OpenAIApiKey;

	UPROPERTY(Config, EditAnywhere, Category = "OpenAI")
	FString OpenAIModel = TEXT("gpt-4.1");

	UPROPERTY(Config, EditAnywhere, Category = "Google", meta = (PasswordField = true))
	FString GoogleApiKey;

	UPROPERTY(Config, EditAnywhere, Category = "Google")
	FString GeminiModel = TEXT("gemini-2.0-flash");

	UPROPERTY(Config, EditAnywhere, Category = "Buffer")
	float ForceOfflineFillAfterSeconds = 4.f;

	UPROPERTY(Config, EditAnywhere, Category = "HTTP")
	float OnlineFirstWaitSeconds = 12.f;

	UPROPERTY(Config, EditAnywhere, Category = "HTTP")
	float OnlineSplitWaitSeconds = 2.f;

	virtual FName GetCategoryName() const override { return FName(TEXT("Game")); }
	virtual FName GetSectionName() const override { return FName(TEXT("AI Quiz")); }
};
