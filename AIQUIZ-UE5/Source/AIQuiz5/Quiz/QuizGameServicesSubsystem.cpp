#include "Quiz/QuizGameServicesSubsystem.h"
#include "Quiz/QuizDeveloperSettings.h"
#include "Quiz/QuizJsonUtils.h"
#include "Quiz/QuizPromptBuilder.h"
#include "Quiz/QuizValidation.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "TimerManager.h"
#include "Async/Async.h"
#include "Misc/DateTime.h"
#include <atomic>

namespace
{
	struct FOnlineBatchCtx
	{
		std::atomic<int32> Remaining{0};
		TArray<FQuizItem> Acc;
		FCriticalSection AccLock;
		TWeakObjectPtr<UQuizGameServicesSubsystem> Sub;
		int32 Wanted = 2;
	};

	static void AppendUniqueQuizzes(TArray<FQuizItem>& Dest, const TArray<FQuizItem>& Src, int32 MaxTotal)
	{
		TSet<FString> Seen;
		for (const FQuizItem& Q : Dest)
		{
			Seen.Add(Q.Question);
		}
		for (const FQuizItem& Q : Src)
		{
			if (Seen.Contains(Q.Question))
			{
				continue;
			}
			Seen.Add(Q.Question);
			Dest.Add(Q);
			if (Dest.Num() >= MaxTotal)
			{
				break;
			}
		}
	}

	static FString QuizEscapeJsonForHttp(const FString& S)
	{
		FString O;
		for (const TCHAR* P = *S; *P; ++P)
		{
			switch (*P)
			{
			case TCHAR('\\'):
				O += TEXT("\\\\");
				break;
			case TCHAR('"'):
				O += TEXT("\\\"");
				break;
			case TCHAR('\n'):
				O += TEXT("\\n");
				break;
			case TCHAR('\r'):
				break;
			default:
				O.AppendChar(*P);
				break;
			}
		}
		return O;
	}

	static FString BuildOpenAIBody(const FString& Model, const FString& Prompt)
	{
		const FString Escaped = QuizEscapeJsonForHttp(Prompt);
		return FString::Printf(
			TEXT("{\"model\":\"%s\",\"temperature\":0.45,\"messages\":[{\"role\":\"user\",\"content\":\"%s\"}]}"),
			*Model,
			*Escaped);
	}

	static FString BuildGeminiBody(const FString& Prompt)
	{
		const FString Escaped = QuizEscapeJsonForHttp(Prompt);
		return FString::Printf(
			TEXT("{\"contents\":[{\"parts\":[{\"text\":\"%s\"}]}],\"generationConfig\":{\"temperature\":0.45,\"responseMimeType\":\"application/json\"}}"),
			*Escaped);
	}

	static FString ExtractOpenAIContent(const FString& JsonStr)
	{
		TSharedPtr<FJsonValue> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || Root->Type != EJson::Object)
		{
			return FString();
		}
		const TSharedPtr<FJsonObject> O = Root->AsObject();
		const TArray<TSharedPtr<FJsonValue>> Ch = O->GetArrayField(TEXT("choices"));
		if (Ch.Num() == 0 || !Ch[0].IsValid() || Ch[0]->Type != EJson::Object)
		{
			return FString();
		}
		const TSharedPtr<FJsonObject> Choice0 = Ch[0]->AsObject();
		const TSharedPtr<FJsonObject> Msg = Choice0->GetObjectField(TEXT("message"));
		if (!Msg.IsValid())
		{
			return FString();
		}
		return Msg->GetStringField(TEXT("content"));
	}

	static FString ExtractGeminiText(const FString& JsonStr)
	{
		TSharedPtr<FJsonValue> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || Root->Type != EJson::Object)
		{
			return FString();
		}
		const TSharedPtr<FJsonObject> O = Root->AsObject();
		const TArray<TSharedPtr<FJsonValue>> Cand = O->GetArrayField(TEXT("candidates"));
		if (Cand.Num() == 0 || !Cand[0].IsValid() || Cand[0]->Type != EJson::Object)
		{
			return FString();
		}
		const TSharedPtr<FJsonObject> C0 = Cand[0]->AsObject();
		const TSharedPtr<FJsonObject> Content = C0->GetObjectField(TEXT("content"));
		if (!Content.IsValid())
		{
			return FString();
		}
		const TArray<TSharedPtr<FJsonValue>> Parts = Content->GetArrayField(TEXT("parts"));
		if (Parts.Num() == 0)
		{
			return FString();
		}
		FString Txt;
		if (Parts[0]->TryGetString(Txt))
		{
			return Txt;
		}
		return FString();
	}

	static FRatingsBuckets RatingsBucketsFromRoot(const TSharedPtr<FJsonObject>& Root)
	{
		FRatingsBuckets B;
		if (!Root.IsValid())
		{
			return B;
		}
		const TArray<TSharedPtr<FJsonValue>>* G = nullptr;
		if (Root->TryGetArrayField(TEXT("good"), G) && G)
		{
			for (const TSharedPtr<FJsonValue>& V : *G)
			{
				if (V.IsValid() && V->Type == EJson::Object)
				{
					B.Good.Add(V->AsObject());
				}
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Bad = nullptr;
		if (Root->TryGetArrayField(TEXT("bad"), Bad) && Bad)
		{
			for (const TSharedPtr<FJsonValue>& V : *Bad)
			{
				if (V.IsValid() && V->Type == EJson::Object)
				{
					B.Bad.Add(V->AsObject());
				}
			}
		}
		return B;
	}

	static bool RatingsHasEntry(const TArray<TSharedPtr<FJsonValue>>& Arr, const FString& Q, const FString& Subj, const FString& Gr)
	{
		for (const TSharedPtr<FJsonValue>& V : Arr)
		{
			if (!V.IsValid() || V->Type != EJson::Object)
			{
				continue;
			}
			const TSharedPtr<FJsonObject> O = V->AsObject();
			if (O->GetStringField(TEXT("q")).TrimStartAndEnd() != Q.TrimStartAndEnd())
			{
				continue;
			}
			if (O->GetStringField(TEXT("subject")).TrimStartAndEnd() != Subj.TrimStartAndEnd())
			{
				continue;
			}
			if (O->GetStringField(TEXT("grade")).TrimStartAndEnd() != Gr.TrimStartAndEnd())
			{
				continue;
			}
			return true;
		}
		return false;
	}
}

void UQuizGameServicesSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	const UQuizDeveloperSettings* S = GetDefault<UQuizDeveloperSettings>();
	OpenAIApiKey = S->OpenAIApiKey;
	OpenAIModel = S->OpenAIModel;
	GoogleApiKey = S->GoogleApiKey;
	GeminiModel = S->GeminiModel;
	ForceOfflineFillAfterSeconds = S->ForceOfflineFillAfterSeconds;
	OnlineFirstWaitSeconds = S->OnlineFirstWaitSeconds;
	OnlineSplitWaitSeconds = S->OnlineSplitWaitSeconds;

	OfflineBank.LoadFromFile(ResolveBankPath());
	LoadRatings();
	TryStartWorkerTimer();
}

void UQuizGameServicesSubsystem::Deinitialize()
{
	if (UGameInstance* GI = GetGameInstance())
	{
		if (UWorld* W = GI->GetWorld())
		{
			W->GetTimerManager().ClearTimer(WorkerTimerHandle);
		}
	}
	Super::Deinitialize();
}

void UQuizGameServicesSubsystem::TryStartWorkerTimer()
{
	if (WorkerTimerHandle.IsValid())
	{
		return;
	}
	if (UGameInstance* GI = GetGameInstance())
	{
		if (UWorld* W = GI->GetWorld())
		{
			W->GetTimerManager().SetTimer(
				WorkerTimerHandle,
				FTimerDelegate::CreateUObject(this, &UQuizGameServicesSubsystem::WorkerTick),
				0.04f,
				true);
		}
	}
}

void UQuizGameServicesSubsystem::EnsureWorkerTimer()
{
	TryStartWorkerTimer();
}

FString UQuizGameServicesSubsystem::ResolveBankPath() const
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir() / TEXT("Data/offline_bank.json"));
}

FString UQuizGameServicesSubsystem::ResolveRatingsPath() const
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("quiz_ratings.json"));
}

FString UQuizGameServicesSubsystem::ResolveRejectLogPath() const
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("quiz_generation_reject_log.jsonl"));
}

FString UQuizGameServicesSubsystem::ResolveSourceLogPath() const
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("quiz_generation_log.jsonl"));
}

void UQuizGameServicesSubsystem::LoadRatings()
{
	FString JsonStr;
	RatingsRoot = MakeShared<FJsonObject>();
	RatingsRoot->SetArrayField(TEXT("good"), {});
	RatingsRoot->SetArrayField(TEXT("bad"), {});
	if (FFileHelper::LoadFileToString(JsonStr, *ResolveRatingsPath()))
	{
		TSharedPtr<FJsonValue> V;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
		if (FJsonSerializer::Deserialize(Reader, V) && V.IsValid() && V->Type == EJson::Object)
		{
			RatingsRoot = V->AsObject();
			if (!RatingsRoot->HasField(TEXT("good")))
			{
				RatingsRoot->SetArrayField(TEXT("good"), {});
			}
			if (!RatingsRoot->HasField(TEXT("bad")))
			{
				RatingsRoot->SetArrayField(TEXT("bad"), {});
			}
		}
	}
}

void UQuizGameServicesSubsystem::SaveRatings()
{
	if (!RatingsRoot.IsValid())
	{
		return;
	}
	FString Out;
	const TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Out);
	FJsonSerializer::Serialize(RatingsRoot.ToSharedRef(), W);
	FFileHelper::SaveStringToFile(Out, *ResolveRatingsPath());
}

void UQuizGameServicesSubsystem::AppendJsonl(const FString& Path, const TSharedPtr<FJsonObject>& LineObj)
{
	if (!LineObj.IsValid())
	{
		return;
	}
	FString Line;
	const TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Line);
	FJsonSerializer::Serialize(LineObj.ToSharedRef(), W);
	Line += TEXT("\n");
	FFileHelper::SaveStringToFile(Line, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_Append);
}

void UQuizGameServicesSubsystem::SetLlmOnline(bool bOnline)
{
	bLlmOnline = bOnline;
}

void UQuizGameServicesSubsystem::BeginRound(
	const FString& Subject,
	int32 Grade,
	const FString& Difficulty,
	const FString& Mode,
	int32 TargetCount)
{
	ActiveSubject = Subject;
	ActiveGrade = Grade;
	ActiveDifficulty = Difficulty;
	ActiveMode = Mode;
	ActiveTargetCount = TargetCount;
	PreloadStartedAt = FPlatformTime::Seconds();
	OnlineFailStreak = 0;
	OnlineBackoffUntil = 0;
	AdaptiveRelax = 0.f;
	RecentQuestions.Empty();
	PlayHistory.Empty();
	{
		FScopeLock L(&BufferLock);
		Buffer.Empty();
		Inflight = 0;
	}
}

TArray<FQuizItem> UQuizGameServicesSubsystem::PullQuizzes(int32 Count)
{
	return PullManyLocked(FMath::Max(1, Count));
}

TArray<FQuizItem> UQuizGameServicesSubsystem::PullManyLocked(int32 Count)
{
	FScopeLock L(&BufferLock);
	TArray<FQuizItem> Out;
	while (Buffer.Num() > 0 && Out.Num() < Count)
	{
		Out.Add(Buffer[0]);
		Buffer.RemoveAt(0);
	}
	return Out;
}

int32 UQuizGameServicesSubsystem::GetBufferedCount() const
{
	FScopeLock L(&BufferLock);
	return Buffer.Num();
}

int32 UQuizGameServicesSubsystem::GetInflightCount() const
{
	FScopeLock L(&BufferLock);
	return Inflight;
}

bool UQuizGameServicesSubsystem::IsReadyForMode() const
{
	FScopeLock L(&BufferLock);
	if (ActiveMode == QuizConst::ModeTen)
	{
		return Buffer.Num() >= FMath::Min(10, ActiveTargetCount);
	}
	return Buffer.Num() >= 1;
}

void UQuizGameServicesSubsystem::MarkInflight(int32 Delta)
{
	FScopeLock L(&BufferLock);
	Inflight = FMath::Max(0, Inflight + Delta);
}

void UQuizGameServicesSubsystem::PushQuiz(const FQuizItem& Q)
{
	FScopeLock L(&BufferLock);
	Buffer.Add(Q);
}

int32 UQuizGameServicesSubsystem::TargetBufferSize() const
{
	return ActiveMode == QuizConst::ModeTen ? 10 : 4;
}

bool UQuizGameServicesSubsystem::WorkerShouldFill() const
{
	FScopeLock L(&BufferLock);
	return Buffer.Num() + Inflight < TargetBufferSize();
}

bool UQuizGameServicesSubsystem::ShouldForceOfflineFill() const
{
	if (!bLlmOnline || ForceOfflineFillAfterSeconds <= 0.f)
	{
		return false;
	}
	const double Elapsed = FPlatformTime::Seconds() - PreloadStartedAt;
	if (Elapsed < ForceOfflineFillAfterSeconds)
	{
		return false;
	}
	FScopeLock L(&BufferLock);
	const int32 Pending = Buffer.Num() + Inflight;
	if (ActiveMode == QuizConst::ModeTen)
	{
		return Pending < FMath::Max(2, FMath::Min(4, ActiveTargetCount));
	}
	return Pending < 1;
}

void UQuizGameServicesSubsystem::SubmitResult(const FQuizItem* Quiz, bool bCorrect)
{
	RecentResults.Add(bCorrect);
	if (RecentResults.Num() >= 6)
	{
		int32 Ok = 0;
		for (bool B : RecentResults)
		{
			if (B)
			{
				++Ok;
			}
		}
		const float R = static_cast<float>(Ok) / static_cast<float>(RecentResults.Num());
		if (R < 0.35f)
		{
			AdaptiveRelax = FMath::Min(0.18f, AdaptiveRelax + 0.03f);
		}
		else if (R > 0.75f)
		{
			AdaptiveRelax = FMath::Max(0.f, AdaptiveRelax - 0.02f);
		}
	}
	if (Quiz && !Quiz->Question.IsEmpty())
	{
		PlayHistory.Add(Quiz->Question);
		if (PlayHistory.Num() > 90)
		{
			PlayHistory.RemoveAt(0, PlayHistory.Num() - 90);
		}
	}
}

void UQuizGameServicesSubsystem::MarkQuizGood(
	const FQuizItem& Quiz,
	const FString& Subject,
	int32 Grade,
	const FString& Difficulty)
{
	LoadRatings();
	if (!RatingsRoot.IsValid())
	{
		return;
	}
	if (!RatingsRoot->HasField(TEXT("good")))
	{
		RatingsRoot->SetArrayField(TEXT("good"), {});
	}
	TArray<TSharedPtr<FJsonValue>> Good = RatingsRoot->GetArrayField(TEXT("good"));
	const FString Gr = FString::FromInt(Grade);
	if (RatingsHasEntry(Good, Quiz.Question, Subject, Gr))
	{
		return;
	}
	const TSharedPtr<FJsonObject> E = MakeShared<FJsonObject>();
	E->SetStringField(TEXT("q"), Quiz.Question);
	E->SetStringField(TEXT("subject"), Subject);
	E->SetStringField(TEXT("grade"), Gr);
	E->SetStringField(TEXT("difficulty"), Difficulty);
	E->SetNumberField(TEXT("ts"), static_cast<double>(FDateTime::UtcNow().ToUnixTimestamp()));
	Good.Add(MakeShared<FJsonValueObject>(E));
	RatingsRoot->SetArrayField(TEXT("good"), Good);
	SaveRatings();
}

void UQuizGameServicesSubsystem::MarkQuizBad(
	const FQuizItem& Quiz,
	const FString& Subject,
	int32 Grade,
	const FString& Difficulty)
{
	LoadRatings();
	if (!RatingsRoot.IsValid())
	{
		return;
	}
	if (!RatingsRoot->HasField(TEXT("bad")))
	{
		RatingsRoot->SetArrayField(TEXT("bad"), {});
	}
	TArray<TSharedPtr<FJsonValue>> Bad = RatingsRoot->GetArrayField(TEXT("bad"));
	const FString Gr = FString::FromInt(Grade);
	if (RatingsHasEntry(Bad, Quiz.Question, Subject, Gr))
	{
		return;
	}
	const TSharedPtr<FJsonObject> E = MakeShared<FJsonObject>();
	E->SetStringField(TEXT("q"), Quiz.Question);
	E->SetStringField(TEXT("subject"), Subject);
	E->SetStringField(TEXT("grade"), Gr);
	E->SetStringField(TEXT("difficulty"), Difficulty);
	E->SetNumberField(TEXT("ts"), static_cast<double>(FDateTime::UtcNow().ToUnixTimestamp()));
	Bad.Add(MakeShared<FJsonValueObject>(E));
	RatingsRoot->SetArrayField(TEXT("bad"), Bad);
	SaveRatings();
}

FString UQuizGameServicesSubsystem::ValidateQuiz(const FQuizItem& Quiz) const
{
	const FRatingsBuckets R = RatingsBucketsFromRoot(RatingsRoot);
	if (FQuizValidation::IsBadRatedQuestion(R, Quiz, ActiveSubject, ActiveGrade))
	{
		return TEXT("bad_rated_question");
	}
	const FString Fit = FQuizValidation::GradeFitRejectReason(Quiz, ActiveSubject, ActiveGrade, ActiveDifficulty, AdaptiveRelax);
	if (!Fit.IsEmpty())
	{
		return Fit;
	}
	if (ActiveMode == QuizConst::ModeTen && RecentQuestions.Num() >= FMath::Max(0, ActiveTargetCount - 1))
	{
		return FString();
	}
	if (FQuizValidation::IsSimilarQuestion(Quiz, RecentQuestions))
	{
		return TEXT("similar_question");
	}
	return FString();
}

void UQuizGameServicesSubsystem::ProcessFetchedBatch(TArray<FQuizItem> Items)
{
	for (int32 i = 0; i < Items.Num(); ++i)
	{
		const int32 J = FMath::RandRange(i, Items.Num() - 1);
		Items.Swap(i, J);
	}
	for (const FQuizItem& Q : Items)
	{
		const FString Reason = ValidateQuiz(Q);
		if (!Reason.IsEmpty())
		{
			const TSharedPtr<FJsonObject> L = MakeShared<FJsonObject>();
			L->SetNumberField(TEXT("t"), static_cast<double>(FDateTime::UtcNow().ToUnixTimestamp()));
			L->SetNumberField(TEXT("player"), 1);
			L->SetStringField(TEXT("subject"), ActiveSubject);
			L->SetNumberField(TEXT("grade"), ActiveGrade);
			L->SetStringField(TEXT("difficulty"), ActiveDifficulty);
			L->SetStringField(TEXT("reason"), Reason);
			L->SetStringField(TEXT("q"), Q.Question);
			L->SetStringField(TEXT("src"), Q.Source);
			AppendJsonl(ResolveRejectLogPath(), L);
			continue;
		}
		const TSharedPtr<FJsonObject> L2 = MakeShared<FJsonObject>();
		L2->SetNumberField(TEXT("t"), static_cast<double>(FDateTime::UtcNow().ToUnixTimestamp()));
		L2->SetNumberField(TEXT("player"), 1);
		L2->SetStringField(TEXT("subject"), ActiveSubject);
		L2->SetNumberField(TEXT("grade"), ActiveGrade);
		L2->SetStringField(TEXT("difficulty"), ActiveDifficulty);
		L2->SetStringField(TEXT("q"), Q.Question);
		L2->SetStringField(TEXT("src"), Q.Source);
		AppendJsonl(ResolveSourceLogPath(), L2);
		RecentQuestions.Add(Q.Question);
		if (RecentQuestions.Num() > 80)
		{
			RecentQuestions.RemoveAt(0, RecentQuestions.Num() - 80);
		}
		PushQuiz(Q);
	}
}

TArray<FQuizItem> UQuizGameServicesSubsystem::FetchOfflineBatch(int32 Count)
{
	return OfflineBank.GetQuizzes(ActiveSubject, ActiveGrade, ActiveDifficulty, ActiveMode, FMath::Max(1, Count));
}

void UQuizGameServicesSubsystem::LaunchOnlineHttp(int32 Count)
{
	int32 NumPending = 0;
	if (!OpenAIApiKey.IsEmpty())
	{
		++NumPending;
	}
	if (!GoogleApiKey.IsEmpty())
	{
		++NumPending;
	}
	if (NumPending == 0)
	{
		MarkInflight(-1);
		return;
	}

	const TSharedPtr<FOnlineBatchCtx> Ctx = MakeShared<FOnlineBatchCtx>();
	Ctx->Sub = this;
	Ctx->Wanted = Count;
	Ctx->Remaining.store(NumPending);

	TArray<FString> Hist = PlayHistory;
	TArray<TSharedPtr<FJsonObject>> GoodEx;
	TArray<TSharedPtr<FJsonObject>> BadEx;
	if (RatingsRoot.IsValid())
	{
		const TArray<TSharedPtr<FJsonValue>>* G = nullptr;
		if (RatingsRoot->TryGetArrayField(TEXT("good"), G) && G)
		{
			for (const TSharedPtr<FJsonValue>& V : *G)
			{
				if (V.IsValid() && V->Type == EJson::Object)
				{
					GoodEx.Add(V->AsObject());
				}
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* B = nullptr;
		if (RatingsRoot->TryGetArrayField(TEXT("bad"), B) && B)
		{
			for (const TSharedPtr<FJsonValue>& V : *B)
			{
				if (V.IsValid() && V->Type == EJson::Object)
				{
					BadEx.Add(V->AsObject());
				}
			}
		}
	}
	const FString Prompt = FQuizPromptBuilder::BuildOnlinePrompt(
		ActiveSubject,
		ActiveGrade,
		ActiveDifficulty,
		Count,
		Hist,
		GoodEx,
		BadEx);

	auto FinishOne = [Ctx](const FString& Content)
	{
		const TArray<FQuizItem> Parsed = FQuizJsonUtils::ExtractQuizzesFromText(Content);
		{
			FScopeLock L(&Ctx->AccLock);
			AppendUniqueQuizzes(Ctx->Acc, Parsed, Ctx->Wanted * 2);
		}
		const int32 Prev = Ctx->Remaining.fetch_sub(1);
		if (Prev == 1)
		{
			TWeakObjectPtr<UQuizGameServicesSubsystem> W = Ctx->Sub;
			TArray<FQuizItem> Copy;
			{
				FScopeLock L(&Ctx->AccLock);
				Copy = Ctx->Acc;
			}
			AsyncTask(ENamedThreads::GameThread, [W, Copy]() {
				if (UQuizGameServicesSubsystem* S = W.Get())
				{
					S->MarkInflight(-1);
					if (Copy.Num() > 0)
					{
						S->OnlineFailStreak = 0;
						S->OnlineBackoffUntil = 0;
						S->ProcessFetchedBatch(Copy);
					}
					else
					{
						S->OnlineFailStreak = FMath::Min(8, S->OnlineFailStreak + 1);
						const double Now = FPlatformTime::Seconds();
						S->OnlineBackoffUntil = Now + FMath::Min(4.0, 0.5 * FMath::Pow(2.0, FMath::Max(0, S->OnlineFailStreak - 1)));
					}
				}
			});
		}
	};

	if (!OpenAIApiKey.IsEmpty())
	{
		TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
		Req->SetURL(TEXT("https://api.openai.com/v1/chat/completions"));
		Req->SetVerb(TEXT("POST"));
		Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
		Req->SetHeader(TEXT("Authorization"), FString::Printf(TEXT("Bearer %s"), *OpenAIApiKey));
		Req->SetContentAsString(BuildOpenAIBody(OpenAIModel, Prompt));
		Req->SetTimeout(25.f);
		Req->OnProcessRequestComplete().BindLambda([FinishOne](FHttpRequestPtr R, FHttpResponsePtr Resp, bool bOk) {
			FString Content;
			if (bOk && Resp.IsValid() && Resp->GetResponseCode() >= 200 && Resp->GetResponseCode() < 300)
			{
				Content = ExtractOpenAIContent(Resp->GetContentAsString());
			}
			FinishOne(Content);
		});
		Req->ProcessRequest();
	}

	if (!GoogleApiKey.IsEmpty())
	{
		const FString Url = FString::Printf(
			TEXT("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"),
			*GeminiModel,
			*GoogleApiKey);
		TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req2 = FHttpModule::Get().CreateRequest();
		Req2->SetURL(Url);
		Req2->SetVerb(TEXT("POST"));
		Req2->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
		Req2->SetContentAsString(BuildGeminiBody(Prompt));
		Req2->SetTimeout(25.f);
		Req2->OnProcessRequestComplete().BindLambda([FinishOne](FHttpRequestPtr R, FHttpResponsePtr Resp, bool bOk) {
			FString Content;
			if (bOk && Resp.IsValid() && Resp->GetResponseCode() >= 200 && Resp->GetResponseCode() < 300)
			{
				Content = ExtractGeminiText(Resp->GetContentAsString());
			}
			FinishOne(Content);
		});
		Req2->ProcessRequest();
	}
}

void UQuizGameServicesSubsystem::WorkerTick()
{
	if (!WorkerShouldFill())
	{
		return;
	}
	MarkInflight(1);
	const bool ForceOffline = ShouldForceOfflineFill();
	if (bLlmOnline && !ForceOffline)
	{
		const double Now = FPlatformTime::Seconds();
		if (Now < OnlineBackoffUntil)
		{
			MarkInflight(-1);
			return;
		}
		if (Now - LastOnlineAttempt < 0.25)
		{
			MarkInflight(-1);
			return;
		}
		LastOnlineAttempt = Now;
		LaunchOnlineHttp(2);
	}
	else
	{
		int32 OfflineBatch = 2;
		if (ActiveMode == QuizConst::ModeTen)
		{
			OfflineBatch = FMath::Clamp(ActiveTargetCount, 6, 10);
		}
		const TArray<FQuizItem> Fetched = FetchOfflineBatch(OfflineBatch);
		MarkInflight(-1);
		ProcessFetchedBatch(Fetched);
	}
}
