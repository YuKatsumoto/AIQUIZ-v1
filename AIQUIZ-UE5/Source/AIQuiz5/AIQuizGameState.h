#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "Quiz/QuizConstants.h"
#include "Quiz/QuizTypes.h"
#include "AIQuizGameState.generated.h"

class UQuizGameServicesSubsystem;
class AQuizPlayerVisual;
class AQuizWallVisual;

UCLASS()
class AAIQuizGameState : public AGameStateBase
{
	GENERATED_BODY()

public:
	AAIQuizGameState();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	void SetMoveAxis(float V) { MoveAxis = FMath::Clamp(V, -1.f, 1.f); }

	void MenuSelectModeTen();
	void MenuSelectModeEndless();
	void MenuContinueSettings();
	void MenuToggleLlmOnline();
	void MenuCycleSubject(int32 Delta);
	void MenuCycleGrade(int32 Delta);
	void MenuCycleDifficulty(int32 Delta);
	void MenuStartGame();

	void RequestBackToModeSelect();
	void RequestResetToMenu();

	void HudClickRatingGood();
	void HudClickRatingBad();

	FString GetUiGameState() const { return GameState; }
	FString GetMenuStep() const { return MenuStep; }
	FString GetSubject() const { return Subject; }
	int32 GetGrade() const { return Grade; }
	FString GetDifficulty() const { return Difficulty; }
	FString GetMode() const { return Mode; }
	bool IsLlmOnlineUi() const { return bLlmOnlineUi; }
	int32 GetScore() const { return Score; }
	int32 GetCurrentIndex() const { return CurrentIndex; }
	FQuizItem GetCurrentQuiz() const { return CurrentQuiz; }
	FString GetMessageText() const { return MessageText; }
	FString GetStatusText() const { return StatusText; }
	float GetPlayerX() const { return PlayerX; }
	float GetWallZ() const { return WallZ; }
	const FGameTuning& GetTuning() const { return Tuning; }

private:
	void GameUpdate(float Dt);
	void LoadCurrentQuiz();
	void ResolveCollision();
	void AdvanceAfterCorrect();
	void GameOver(const FString& Msg);
	void ClearGame();
	void RefreshStatusText();
	void SyncVisuals();

	UQuizGameServicesSubsystem* QuizSubsystem = nullptr;

	float MoveAxis = 0.f;
	float Accumulator = 0.f;
	const float FixedDt = 1.f / 60.f;

	FGameTuning Tuning;

	FString GameState = QuizConst::StateMenu;
	FString MenuStep = QuizConst::MenuStepMode;
	FString Subject = TEXT("算数");
	int32 Grade = 3;
	FString Difficulty = TEXT("普通");
	FString Mode = QuizConst::ModeTen;
	bool bLlmOnlineUi = false;

	int32 Score = 0;
	int32 CurrentIndex = 0;
	TArray<FQuizItem> QuizList;
	FQuizItem CurrentQuiz;

	bool bChoiceLocked = false;
	float MessageTimer = 0.f;
	float PlayerX = 0.f;
	float WallZ = 22.f;
	FString MessageText;
	FString StatusText;
	float CorrectFlash = 0.f;
	float WrongFlash = 0.f;
	float CameraShake = 0.f;
	float PreloadWaitSec = 0.f;
	float MinPreloadSec = 0.35f;
	int32 TargetCount = 10;
	bool bRatingTargetValid = false;
	FQuizItem RatingTargetQuiz;
	FString RatingFeedback;

	UPROPERTY()
	AQuizPlayerVisual* PlayerVisual = nullptr;

	UPROPERTY()
	AQuizWallVisual* WallVisual = nullptr;
};
