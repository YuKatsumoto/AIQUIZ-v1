#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "Quiz/QuizMainWidget.h"
#include "AIQuizPlayerController.generated.h"

UCLASS()
class AAIQuizPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	virtual void PlayerTick(float DeltaTime) override;

private:
	void OnMoveAxis(float V);
	void OnResetMenu();
	void OnEscape();

	UPROPERTY()
	TObjectPtr<UQuizMainWidget> HudWidget;
};
