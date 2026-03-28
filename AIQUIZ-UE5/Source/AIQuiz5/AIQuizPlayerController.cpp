#include "AIQuizPlayerController.h"
#include "AIQuizGameState.h"
#include "Quiz/QuizConstants.h"
#include "Blueprint/UserWidget.h"

void AAIQuizPlayerController::BeginPlay()
{
	Super::BeginPlay();
	bShowMouseCursor = true;
	bEnableClickEvents = true;
	bEnableMouseOverEvents = true;
	if (UQuizMainWidget* W = CreateWidget<UQuizMainWidget>(this, UQuizMainWidget::StaticClass()))
	{
		HudWidget = W;
		W->AddToViewport(0);
		FInputModeGameAndUI Mode;
		Mode.SetWidgetToFocus(W->TakeWidget());
		Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
		SetInputMode(Mode);
	}
}

void AAIQuizPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();
	InputComponent->BindAxis(TEXT("MoveAxis"), this, &AAIQuizPlayerController::OnMoveAxis);
	InputComponent->BindAction(TEXT("ResetMenu"), IE_Pressed, this, &AAIQuizPlayerController::OnResetMenu);
	InputComponent->BindAction(TEXT("PauseEscape"), IE_Pressed, this, &AAIQuizPlayerController::OnEscape);
}

void AAIQuizPlayerController::PlayerTick(const float DeltaTime)
{
	Super::PlayerTick(DeltaTime);
	if (AAIQuizGameState* GS = GetWorld()->GetGameState<AAIQuizGameState>())
	{
		const float Axis = InputComponent ? InputComponent->GetAxisValue(TEXT("MoveAxis")) : 0.f;
		GS->SetMoveAxis(Axis);
	}
}

void AAIQuizPlayerController::OnMoveAxis(const float V)
{
	if (AAIQuizGameState* GS = GetWorld()->GetGameState<AAIQuizGameState>())
	{
		GS->SetMoveAxis(V);
	}
}

void AAIQuizPlayerController::OnResetMenu()
{
	if (AAIQuizGameState* GS = GetWorld()->GetGameState<AAIQuizGameState>())
	{
		if (GS->GetUiGameState() == QuizConst::StateGameOver || GS->GetUiGameState() == QuizConst::StateClear)
		{
			GS->RequestResetToMenu();
		}
	}
}

void AAIQuizPlayerController::OnEscape()
{
	if (AAIQuizGameState* GS = GetWorld()->GetGameState<AAIQuizGameState>())
	{
		if (GS->GetUiGameState() == QuizConst::StatePlaying)
		{
			ConsoleCommand(TEXT("quit"));
		}
	}
}
