#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "QuizVisualActors.generated.h"

UCLASS()
class AQuizPlayerVisual : public AActor
{
	GENERATED_BODY()

public:
	AQuizPlayerVisual();

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Mesh = nullptr;
};

UCLASS()
class AQuizWallVisual : public AActor
{
	GENERATED_BODY()

public:
	AQuizWallVisual();

	UPROPERTY(VisibleAnywhere)
	UStaticMeshComponent* Mesh = nullptr;
};
