#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "AIQuizGameMode.generated.h"

UCLASS()
class AAIQuizGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AAIQuizGameMode();

	virtual void StartPlay() override;
};
