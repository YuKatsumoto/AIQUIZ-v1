#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "QuizConstants.h"
#include "QuizOfflineBank.h"
#include "QuizTypes.h"
#include "QuizGameServicesSubsystem.generated.h"

UCLASS()
class UQuizGameServicesSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	void SetLlmOnline(bool bOnline);
	void BeginRound(const FString& Subject, int32 Grade, const FString& Difficulty, const FString& Mode, int32 TargetCount);

	TArray<FQuizItem> PullQuizzes(int32 Count);
	int32 GetBufferedCount() const;
	int32 GetInflightCount() const;
	bool IsReadyForMode() const;

	void SubmitResult(const FQuizItem* Quiz, bool bCorrect);
	void MarkQuizGood(const FQuizItem& Quiz, const FString& Subject, int32 Grade, const FString& Difficulty);
	void MarkQuizBad(const FQuizItem& Quiz, const FString& Subject, int32 Grade, const FString& Difficulty);

	FString GetSubject() const { return ActiveSubject; }
	int32 GetGrade() const { return ActiveGrade; }
	FString GetDifficulty() const { return ActiveDifficulty; }
	FString GetMode() const { return ActiveMode; }
	int32 GetTargetCount() const { return ActiveTargetCount; }
	bool IsLlmOnline() const { return bLlmOnline; }

	/** Used when completing async HTTP work on the game thread. */
	void MarkInflight(int32 Delta);

	/** World may be null during subsystem Initialize; call from GameMode StartPlay if needed. */
	void EnsureWorkerTimer();

private:
	void TryStartWorkerTimer();
	void WorkerTick();
	void LoadRatings();
	void SaveRatings();
	void AppendJsonl(const FString& Path, const TSharedPtr<FJsonObject>& LineObj);
	FString ResolveBankPath() const;
	FString ResolveRatingsPath() const;
	FString ResolveRejectLogPath() const;
	FString ResolveSourceLogPath() const;

	bool WorkerShouldFill() const;
	int32 TargetBufferSize() const;
	void PushQuiz(const FQuizItem& Q);
	TArray<FQuizItem> PullManyLocked(int32 Count);
	TArray<FQuizItem> FetchOfflineBatch(int32 Count);
	void LaunchOnlineHttp(int32 Count);
	void ProcessFetchedBatch(TArray<FQuizItem> Items);
	FString ValidateQuiz(const FQuizItem& Quiz) const;
	bool ShouldForceOfflineFill() const;

	mutable FCriticalSection BufferLock;
	TArray<FQuizItem> Buffer;
	int32 Inflight = 0;

	FQuizOfflineBank OfflineBank;
	TSharedPtr<FJsonObject> RatingsRoot;

	FTimerHandle WorkerTimerHandle;

	FString ActiveSubject = TEXT("算数");
	int32 ActiveGrade = 3;
	FString ActiveDifficulty = TEXT("普通");
	FString ActiveMode = QuizConst::ModeTen;
	int32 ActiveTargetCount = 10;
	bool bLlmOnline = false;

	double PreloadStartedAt = 0;
	double LastOnlineAttempt = 0;
	double OnlineBackoffUntil = 0;
	int32 OnlineFailStreak = 0;
	float AdaptiveRelax = 0.f;
	TArray<bool> RecentResults;
	TArray<FString> PlayHistory;
	TArray<FString> RecentQuestions;

	FString OpenAIApiKey;
	FString OpenAIModel;
	FString GoogleApiKey;
	FString GeminiModel;
	float ForceOfflineFillAfterSeconds = 4.f;
	float OnlineFirstWaitSeconds = 12.f;
	float OnlineSplitWaitSeconds = 2.f;
};
