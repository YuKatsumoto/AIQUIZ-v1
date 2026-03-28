#pragma once

#include "CoreMinimal.h"

namespace QuizConst
{
	inline const FString StateMenu = TEXT("MENU");
	inline const FString StatePreloading = TEXT("PRELOADING");
	inline const FString StatePlaying = TEXT("PLAYING");
	inline const FString StateCorrect = TEXT("CORRECT");
	inline const FString StateGameOver = TEXT("GAME_OVER");
	inline const FString StateClear = TEXT("CLEAR");

	inline const FString ModeTen = TEXT("TEN_QUESTIONS");
	inline const FString ModeEndless = TEXT("ENDLESS");

	inline const FString MenuStepMode = TEXT("MODE_SELECT");
	inline const FString MenuStepConfig = TEXT("CONFIG_SELECT");

	inline const TArray<FString> Subjects = { TEXT("算数"), TEXT("理科"), TEXT("国語") };
	inline const TArray<FString> Difficulties = { TEXT("簡単"), TEXT("普通"), TEXT("難しい") };
}
