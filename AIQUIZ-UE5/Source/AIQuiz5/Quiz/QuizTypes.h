#pragma once

#include "CoreMinimal.h"
#include "QuizTypes.generated.h"

USTRUCT(BlueprintType)
struct FQuizItem
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString Question;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString Choice0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString Choice1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	int32 AnswerIndex = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString Explanation;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString Source;

	bool IsValidItem() const
	{
		return !Question.IsEmpty() && !Choice0.IsEmpty() && !Choice1.IsEmpty() && (AnswerIndex == 0 || AnswerIndex == 1);
	}
};

USTRUCT(BlueprintType)
struct FGameTuning
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere)
	float PlayerSpeed = 7.6f;

	UPROPERTY(EditAnywhere)
	float MinX = -4.9f;

	UPROPERTY(EditAnywhere)
	float MaxX = 4.9f;

	UPROPERTY(EditAnywhere)
	float WallStartZ = 22.f;

	UPROPERTY(EditAnywhere)
	float WallSpeed = 6.8f;

	UPROPERTY(EditAnywhere)
	float DoorHalfWidth = 1.35f;

	UPROPERTY(EditAnywhere)
	float LeftDoorX = -2.35f;

	UPROPERTY(EditAnywhere)
	float RightDoorX = 2.35f;

	UPROPERTY(EditAnywhere)
	float HitZ = -6.f;

	UPROPERTY(EditAnywhere)
	float CorrectHoldSec = 1.05f;
};
