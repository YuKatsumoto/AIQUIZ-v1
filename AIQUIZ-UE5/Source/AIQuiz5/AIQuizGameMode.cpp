#include "AIQuizGameMode.h"
#include "AIQuizGameState.h"
#include "AIQuizPlayerController.h"
#include "Camera/CameraActor.h"
#include "Engine/World.h"
#include "GameFramework/DefaultPawn.h"
#include "Kismet/GameplayStatics.h"
#include "Quiz/QuizGameServicesSubsystem.h"
#include "Quiz/QuizVisualActors.h"

AAIQuizGameMode::AAIQuizGameMode()
{
	GameStateClass = AAIQuizGameState::StaticClass();
	PlayerControllerClass = AAIQuizPlayerController::StaticClass();
	DefaultPawnClass = ADefaultPawn::StaticClass();
}

void AAIQuizGameMode::StartPlay()
{
	if (UGameInstance* GI = GetGameInstance())
	{
		if (UQuizGameServicesSubsystem* Q = GI->GetSubsystem<UQuizGameServicesSubsystem>())
		{
			Q->EnsureWorkerTimer();
		}
	}
	Super::StartPlay();
	UWorld* W = GetWorld();
	if (!W)
	{
		return;
	}
	if (!UGameplayStatics::GetActorOfClass(W, AQuizPlayerVisual::StaticClass()))
	{
		W->SpawnActor<AQuizPlayerVisual>(FVector(-600.f, 0.f, -65.f), FRotator::ZeroRotator);
	}
	if (!UGameplayStatics::GetActorOfClass(W, AQuizWallVisual::StaticClass()))
	{
		W->SpawnActor<AQuizWallVisual>(FVector(2200.f, 0.f, 45.f), FRotator::ZeroRotator);
	}
	if (!UGameplayStatics::GetActorOfClass(W, ACameraActor::StaticClass()))
	{
		ACameraActor* Cam = W->SpawnActor<ACameraActor>(FVector(-1900.f, 0.f, 630.f), FRotator::ZeroRotator);
		Cam->SetActorRotation(FRotator(-12.f, 0.f, 0.f));
		if (APlayerController* PC = W->GetFirstPlayerController())
		{
			PC->SetViewTargetWithBlend(Cam, 0.f);
		}
	}
}
