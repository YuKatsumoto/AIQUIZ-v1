#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "QuizMainWidget.generated.h"

class UTextBlock;
class UButton;
class UVerticalBox;

UCLASS()
class UQuizMainWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

private:
	UFUNCTION()
	void OnClickModeTen();

	UFUNCTION()
	void OnClickModeEndless();

	UFUNCTION()
	void OnClickToggleLlm();

	UFUNCTION()
	void OnClickSubjectPrev();

	UFUNCTION()
	void OnClickSubjectNext();

	UFUNCTION()
	void OnClickGradePrev();

	UFUNCTION()
	void OnClickGradeNext();

	UFUNCTION()
	void OnClickDiffPrev();

	UFUNCTION()
	void OnClickDiffNext();

	UFUNCTION()
	void OnClickStart();

	UFUNCTION()
	void OnClickBackMode();

	UFUNCTION()
	void OnClickRateGood();

	UFUNCTION()
	void OnClickRateBad();

	UPROPERTY()
	TObjectPtr<UTextBlock> TxtTitle;

	UPROPERTY()
	TObjectPtr<UTextBlock> TxtStatus;

	UPROPERTY()
	TObjectPtr<UTextBlock> TxtQuestion;

	UPROPERTY()
	TObjectPtr<UTextBlock> TxtChoices;

	UPROPERTY()
	TObjectPtr<UTextBlock> TxtMessage;

	UPROPERTY()
	TObjectPtr<UVerticalBox> MenuModeBox;

	UPROPERTY()
	TObjectPtr<UVerticalBox> MenuConfigBox;

	UPROPERTY()
	TObjectPtr<UVerticalBox> RatingBox;

	UPROPERTY()
	TObjectPtr<UButton> BtnModeTen;

	UPROPERTY()
	TObjectPtr<UButton> BtnModeEndless;

	UPROPERTY()
	TObjectPtr<UButton> BtnToggleLlm;

	UPROPERTY()
	TObjectPtr<UButton> BtnStart;

	UPROPERTY()
	TObjectPtr<UButton> BtnBack;

	UPROPERTY()
	TObjectPtr<UButton> BtnRateGood;

	UPROPERTY()
	TObjectPtr<UButton> BtnRateBad;
};
