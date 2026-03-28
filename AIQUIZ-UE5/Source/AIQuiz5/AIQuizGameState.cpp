#include "AIQuizGameState.h"
#include "Quiz/QuizGameServicesSubsystem.h"
#include "Quiz/QuizVisualActors.h"
#include "Engine/GameInstance.h"
#include "Kismet/GameplayStatics.h"

AAIQuizGameState::AAIQuizGameState()
{
	PrimaryActorTick.bCanEverTick = true;
	WallZ = Tuning.WallStartZ;
}

void AAIQuizGameState::BeginPlay()
{
	Super::BeginPlay();
	if (UGameInstance* GI = GetGameInstance())
	{
		QuizSubsystem = GI->GetSubsystem<UQuizGameServicesSubsystem>();
	}
	TArray<AActor*> PFound;
	UGameplayStatics::GetAllActorsOfClass(this, AQuizPlayerVisual::StaticClass(), PFound);
	if (PFound.Num() > 0)
	{
		PlayerVisual = Cast<AQuizPlayerVisual>(PFound[0]);
	}
	TArray<AActor*> WFound;
	UGameplayStatics::GetAllActorsOfClass(this, AQuizWallVisual::StaticClass(), WFound);
	if (WFound.Num() > 0)
	{
		WallVisual = Cast<AQuizWallVisual>(WFound[0]);
	}
	RefreshStatusText();
}

void AAIQuizGameState::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Accumulator += FMath::Min(0.05f, DeltaSeconds);
	while (Accumulator >= FixedDt)
	{
		GameUpdate(FixedDt);
		Accumulator -= FixedDt;
	}
	SyncVisuals();
}

void AAIQuizGameState::GameUpdate(const float Dt)
{
	CorrectFlash = FMath::Max(0.f, CorrectFlash - Dt * 1.5f);
	WrongFlash = FMath::Max(0.f, WrongFlash - Dt * 1.2f);
	CameraShake = FMath::Max(0.f, CameraShake - Dt * 2.8f);

	if (GameState == QuizConst::StateMenu)
	{
		return;
	}
	if (GameState == QuizConst::StateGameOver || GameState == QuizConst::StateClear)
	{
		return;
	}

	if (GameState == QuizConst::StatePreloading)
	{
		PreloadWaitSec += Dt;
		if (!QuizSubsystem)
		{
			return;
		}
		int32 Missing = (Mode == QuizConst::ModeTen) ? FMath::Max(0, TargetCount - QuizList.Num()) : FMath::Max(0, 1 - QuizList.Num());
		if (Missing > 0)
		{
			const TArray<FQuizItem> More = QuizSubsystem->PullQuizzes(Missing);
			QuizList.Append(More);
		}
		const bool Ready = (Mode == QuizConst::ModeTen && QuizList.Num() >= TargetCount)
			|| (Mode == QuizConst::ModeEndless && QuizList.Num() >= 1);
		if (Ready && PreloadWaitSec >= MinPreloadSec)
		{
			GameState = QuizConst::StatePlaying;
			LoadCurrentQuiz();
		}
		else
		{
			MessageText = TEXT("クイズを準備中...");
			RefreshStatusText();
		}
		return;
	}

	if (GameState == QuizConst::StatePlaying)
	{
		PlayerX += MoveAxis * Tuning.PlayerSpeed * Dt;
		PlayerX = FMath::Clamp(PlayerX, Tuning.MinX, Tuning.MaxX);
		WallZ -= Tuning.WallSpeed * Dt;
		if (WallZ <= Tuning.HitZ + 0.45f)
		{
			ResolveCollision();
		}
		return;
	}

	if (GameState == QuizConst::StateCorrect)
	{
		MessageTimer -= Dt;
		if (MessageTimer <= 0.f)
		{
			AdvanceAfterCorrect();
		}
	}
}

static bool IsWithinDoor(const float XPos, const int32 Side, const FGameTuning& T)
{
	const float Center = (Side == 0) ? T.LeftDoorX : T.RightDoorX;
	return FMath::Abs(XPos - Center) <= T.DoorHalfWidth;
}

void AAIQuizGameState::ResolveCollision()
{
	if (!CurrentQuiz.IsValidItem() || bChoiceLocked)
	{
		return;
	}
	bChoiceLocked = true;
	const int32 Answer = CurrentQuiz.AnswerIndex;
	const bool InLeft = IsWithinDoor(PlayerX, 0, Tuning);
	const bool InRight = IsWithinDoor(PlayerX, 1, Tuning);
	if (!InLeft && !InRight)
	{
		GameOver(TEXT("壁にぶつかった！"));
		return;
	}
	if (InLeft && InRight)
	{
		GameOver(TEXT("中央で判定不能！"));
		return;
	}
	const int32 Selected = InLeft ? 0 : 1;
	if (Selected == Answer)
	{
		++Score;
		if (QuizSubsystem)
		{
			QuizSubsystem->SubmitResult(&CurrentQuiz, true);
		}
		GameState = QuizConst::StateCorrect;
		MessageTimer = Tuning.CorrectHoldSec;
		MessageText = TEXT("正解！");
		CorrectFlash = 1.f;
		CameraShake = 0.22f;
	}
	else
	{
		if (QuizSubsystem)
		{
			QuizSubsystem->SubmitResult(&CurrentQuiz, false);
		}
		const FString Explain = CurrentQuiz.Explanation.IsEmpty() ? TEXT("解説なし") : CurrentQuiz.Explanation;
		const FString AnsSide = (Answer == 0) ? TEXT("左") : TEXT("右");
		GameOver(FString::Printf(TEXT("不正解！ 正解は %s\n%s"), *AnsSide, *Explain));
	}
	RefreshStatusText();
}

void AAIQuizGameState::AdvanceAfterCorrect()
{
	if (!QuizSubsystem)
	{
		return;
	}
	if (Mode == QuizConst::ModeTen)
	{
		++CurrentIndex;
		LoadCurrentQuiz();
	}
	else
	{
		QuizList = QuizSubsystem->PullQuizzes(1);
		LoadCurrentQuiz();
	}
	GameState = QuizConst::StatePlaying;
	MessageText.Empty();
	RefreshStatusText();
}

void AAIQuizGameState::GameOver(const FString& Msg)
{
	GameState = QuizConst::StateGameOver;
	bRatingTargetValid = true;
	RatingTargetQuiz = CurrentQuiz;
	RatingFeedback.Empty();
	MessageText = FString::Printf(TEXT("GAME OVER\n\n%s"), *Msg);
	WrongFlash = 1.f;
	CameraShake = 0.35f;
	RefreshStatusText();
}

void AAIQuizGameState::ClearGame()
{
	GameState = QuizConst::StateClear;
	bRatingTargetValid = true;
	RatingTargetQuiz = CurrentQuiz;
	RatingFeedback.Empty();
	MessageText = FString::Printf(TEXT("CLEAR! おめでとう\n10問完走  正解数: %d/10"), Score);
	CorrectFlash = 1.f;
	RefreshStatusText();
}

void AAIQuizGameState::LoadCurrentQuiz()
{
	if (Mode == QuizConst::ModeTen)
	{
		if (CurrentIndex >= QuizList.Num())
		{
			ClearGame();
			return;
		}
		CurrentQuiz = QuizList[CurrentIndex];
	}
	else
	{
		if (QuizList.Num() == 0 && QuizSubsystem)
		{
			QuizList = QuizSubsystem->PullQuizzes(1);
		}
		if (QuizList.Num() == 0)
		{
			return;
		}
		CurrentQuiz = QuizList[0];
	}
	bChoiceLocked = false;
	WallZ = Tuning.WallStartZ;
	PlayerX = 0.f;
	MessageText.Empty();
	RefreshStatusText();
}

void AAIQuizGameState::RefreshStatusText()
{
	if (GameState == QuizConst::StateGameOver || GameState == QuizConst::StateClear)
	{
		StatusText = FString::Printf(TEXT("正解数: %d  |  [R] でメニューへ戻る"), Score);
		return;
	}
	if (GameState == QuizConst::StateMenu)
	{
		if (MenuStep == QuizConst::MenuStepMode)
		{
			StatusText = TEXT("手順 1/3: モードを選択");
		}
		else
		{
			const FString ModeLabel = (Mode == QuizConst::ModeTen) ? TEXT("10問チャレンジ") : TEXT("エンドレス");
			StatusText = FString::Printf(
				TEXT("手順 2/3: 学年・教科を設定  |  モード:%s  教科:%s  学年:%d"),
				*ModeLabel,
				*Subject,
				Grade);
		}
		return;
	}
	if (GameState == QuizConst::StatePreloading)
	{
		if (Mode == QuizConst::ModeTen)
		{
			StatusText = FString::Printf(TEXT("クイズ準備中... %d/%d  教科:%s 学年:%d"), QuizList.Num(), TargetCount, *Subject, Grade);
		}
		else
		{
			StatusText = FString::Printf(TEXT("クイズ準備中... バッファ:%d 教科:%s 学年:%d"), QuizList.Num(), *Subject, Grade);
		}
		return;
	}
	const FString ModeLabel = (Mode == QuizConst::ModeTen) ? TEXT("10問チャレンジ") : TEXT("エンドレス");
	const FString Progress = (Mode == QuizConst::ModeTen) ? FString::Printf(TEXT("%d/10"), CurrentIndex + 1) : TEXT("∞");
	StatusText = FString::Printf(
		TEXT("教科:%s  学年:%d  難易度:%s  モード:%s  進行:%s  正解数:%d"),
		*Subject,
		Grade,
		*Difficulty,
		*ModeLabel,
		*Progress,
		Score);
}

void AAIQuizGameState::SyncVisuals()
{
	const float Scale = 100.f;
	const bool bMenu = (GameState == QuizConst::StateMenu);
	if (IsValid(PlayerVisual))
	{
		PlayerVisual->SetActorHiddenInGame(bMenu);
		const FVector Loc(Tuning.HitZ * Scale, PlayerX * Scale, -0.65f * Scale);
		PlayerVisual->SetActorLocation(Loc);
	}
	if (IsValid(WallVisual))
	{
		WallVisual->SetActorHiddenInGame(bMenu);
		if (!bMenu)
		{
			const FVector Loc(WallZ * Scale, 0.f, 0.45f * Scale);
			WallVisual->SetActorLocation(Loc);
		}
	}
}

void AAIQuizGameState::MenuSelectModeTen()
{
	Mode = QuizConst::ModeTen;
	MenuStep = QuizConst::MenuStepConfig;
	RefreshStatusText();
}

void AAIQuizGameState::MenuSelectModeEndless()
{
	Mode = QuizConst::ModeEndless;
	MenuStep = QuizConst::MenuStepConfig;
	RefreshStatusText();
}

void AAIQuizGameState::MenuContinueSettings()
{
	MenuStep = QuizConst::MenuStepConfig;
	RefreshStatusText();
}

void AAIQuizGameState::MenuToggleLlmOnline()
{
	bLlmOnlineUi = !bLlmOnlineUi;
	RefreshStatusText();
}

void AAIQuizGameState::MenuCycleSubject(const int32 Delta)
{
	int32 Idx = QuizConst::Subjects.IndexOfByPredicate([&](const FString& S) { return S == Subject; });
	if (Idx == INDEX_NONE)
	{
		Idx = 0;
	}
	const int32 N = QuizConst::Subjects.Num();
	Idx = ((Idx + Delta) % N + N) % N;
	Subject = QuizConst::Subjects[Idx];
	RefreshStatusText();
}

void AAIQuizGameState::MenuCycleGrade(const int32 Delta)
{
	Grade = FMath::Clamp(Grade + Delta, 1, 6);
	RefreshStatusText();
}

void AAIQuizGameState::MenuCycleDifficulty(const int32 Delta)
{
	int32 Idx = QuizConst::Difficulties.IndexOfByPredicate([&](const FString& S) { return S == Difficulty; });
	if (Idx == INDEX_NONE)
	{
		Idx = 1;
	}
	const int32 N = QuizConst::Difficulties.Num();
	Idx = ((Idx + Delta) % N + N) % N;
	Difficulty = QuizConst::Difficulties[Idx];
	RefreshStatusText();
}

void AAIQuizGameState::MenuStartGame()
{
	Score = 0;
	CurrentIndex = 0;
	const int32 Count = (Mode == QuizConst::ModeTen) ? 10 : 1;
	TargetCount = Count;
	if (QuizSubsystem)
	{
		QuizSubsystem->SetLlmOnline(bLlmOnlineUi);
		QuizSubsystem->BeginRound(Subject, Grade, Difficulty, Mode, Count);
		QuizList = QuizSubsystem->PullQuizzes(Count);
	}
	MessageText.Empty();
	GameState = QuizConst::StatePreloading;
	PreloadWaitSec = 0.f;
	RefreshStatusText();
}

void AAIQuizGameState::RequestBackToModeSelect()
{
	MenuStep = QuizConst::MenuStepMode;
	RefreshStatusText();
}

void AAIQuizGameState::RequestResetToMenu()
{
	GameState = QuizConst::StateMenu;
	MenuStep = QuizConst::MenuStepMode;
	PlayerX = 0.f;
	WallZ = Tuning.WallStartZ;
	MessageText.Empty();
	CorrectFlash = 0.f;
	WrongFlash = 0.f;
	CameraShake = 0.f;
	bRatingTargetValid = false;
	RatingFeedback.Empty();
	RefreshStatusText();
}

void AAIQuizGameState::HudClickRatingGood()
{
	if (!bRatingTargetValid || !QuizSubsystem)
	{
		return;
	}
	QuizSubsystem->MarkQuizGood(RatingTargetQuiz, Subject, Grade, Difficulty);
	RatingFeedback = TEXT("評価: 良い問題");
	bRatingTargetValid = false;
}

void AAIQuizGameState::HudClickRatingBad()
{
	if (!bRatingTargetValid || !QuizSubsystem)
	{
		return;
	}
	QuizSubsystem->MarkQuizBad(RatingTargetQuiz, Subject, Grade, Difficulty);
	RatingFeedback = TEXT("評価: 悪い問題");
	bRatingTargetValid = false;
}
