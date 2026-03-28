#include "Quiz/QuizJsonUtils.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

bool FQuizJsonUtils::TryParseQuizObject(const TSharedPtr<FJsonObject>& Obj, FQuizItem& Out, const FString& SrcLabel)
{
	if (!Obj.IsValid())
	{
		return false;
	}
	FString Q = Obj->GetStringField(TEXT("q")).TrimStartAndEnd();
	const TArray<TSharedPtr<FJsonValue>>* CArr = nullptr;
	if (!Obj->TryGetArrayField(TEXT("c"), CArr) || !CArr || CArr->Num() != 2)
	{
		return false;
	}
	FString C0, C1;
	if (!(*CArr)[0]->TryGetString(C0) || !(*CArr)[1]->TryGetString(C1))
	{
		return false;
	}
	C0.TrimStartAndEndInline();
	C1.TrimStartAndEndInline();
	double ADbl = 0;
	if (!Obj->TryGetNumberField(TEXT("a"), ADbl))
	{
		return false;
	}
	const int32 A = FMath::RoundToInt(ADbl);
	if (A != 0 && A != 1)
	{
		return false;
	}
	if (Q.IsEmpty() || C0.IsEmpty() || C1.IsEmpty())
	{
		return false;
	}
	FString E = Obj->GetStringField(TEXT("e"));
	if (E.IsEmpty())
	{
		E = Obj->GetStringField(TEXT("exp"));
	}
	E.TrimStartAndEndInline();
	Out.Question = Q;
	Out.Choice0 = C0;
	Out.Choice1 = C1;
	Out.AnswerIndex = A;
	Out.Explanation = E;
	Out.Source = SrcLabel;
	return true;
}

TArray<TSharedPtr<FJsonValue>> FQuizJsonUtils::ExtractJsonArrayFromText(const FString& RawText)
{
	TArray<TSharedPtr<FJsonValue>> Result;
	const FString T = RawText.TrimStartAndEnd();
	if (T.IsEmpty())
	{
		return Result;
	}
	auto TryDecodeFrom = [&](int32 StartIdx) -> bool
	{
		const FString Sub = T.Mid(StartIdx);
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Sub);
		TSharedPtr<FJsonValue> Root;
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			return false;
		}
		if (Root->Type == EJson::Array)
		{
			Result = Root->AsArray();
			return true;
		}
		if (Root->Type == EJson::Object)
		{
			const TSharedPtr<FJsonObject> O = Root->AsObject();
			const TArray<TSharedPtr<FJsonValue>>* Quizzes = nullptr;
			if (O->TryGetArrayField(TEXT("quizzes"), Quizzes) && Quizzes)
			{
				Result = *Quizzes;
				return true;
			}
		}
		return false;
	};

	TArray<int32> Starts;
	for (int32 i = 0; i < T.Len(); ++i)
	{
		const TCHAR C = T[i];
		if (C == TCHAR('[') || C == TCHAR('{'))
		{
			Starts.Add(i);
		}
	}
	Starts.Sort();
	for (int32 S : Starts)
	{
		if (TryDecodeFrom(S))
		{
			break;
		}
	}
	return Result;
}

TArray<FQuizItem> FQuizJsonUtils::ExtractQuizzesFromText(const FString& RawText)
{
	TArray<FQuizItem> Out;
	const TArray<TSharedPtr<FJsonValue>> Arr = ExtractJsonArrayFromText(RawText);
	for (const TSharedPtr<FJsonValue>& V : Arr)
	{
		if (!V.IsValid() || V->Type != EJson::Object)
		{
			continue;
		}
		FQuizItem Item;
		if (TryParseQuizObject(V->AsObject(), Item, TEXT("JSON")))
		{
			Out.Add(Item);
		}
	}
	return Out;
}
