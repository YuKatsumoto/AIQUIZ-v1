#include "Quiz/QuizMainWidget.h"
#include "AIQuizGameState.h"
#include "Quiz/QuizConstants.h"
#include "Components/Button.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Blueprint/WidgetTree.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Internationalization/Text.h"

void UQuizMainWidget::NativeConstruct()
{
	Super::NativeConstruct();
	UWidgetTree* Tree = WidgetTree.Get();
	if (!Tree)
	{
		return;
	}
	if (Tree->RootWidget)
	{
		Tree->RemoveWidget(Tree->RootWidget);
		Tree->RootWidget = nullptr;
	}
	UVerticalBox* Root = Tree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Root")));
	Tree->RootWidget = Root;

	TxtTitle = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Title"));
	TxtTitle->SetText(FText::FromString(TEXT("AI脱出クイズ 3D (UE5)")));
	Root->AddChildToVerticalBox(TxtTitle);

	TxtStatus = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Status"));
	TxtStatus->SetAutoWrapText(true);
	Root->AddChildToVerticalBox(TxtStatus);

	MenuModeBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("MenuMode"));
	BtnModeTen = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("BtnTen"));
	UTextBlock* Lt = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Lt"));
	Lt->SetText(FText::FromString(TEXT("10問チャレンジ")));
	BtnModeTen->AddChild(Lt);
	BtnModeTen->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickModeTen);
	MenuModeBox->AddChildToVerticalBox(BtnModeTen);

	BtnModeEndless = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("BtnEnd"));
	UTextBlock* Le = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Le"));
	Le->SetText(FText::FromString(TEXT("エンドレス")));
	BtnModeEndless->AddChild(Le);
	BtnModeEndless->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickModeEndless);
	MenuModeBox->AddChildToVerticalBox(BtnModeEndless);
	Root->AddChildToVerticalBox(MenuModeBox);

	MenuConfigBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("MenuConfig"));
	BtnToggleLlm = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("BtnLlm"));
	UTextBlock* LlmT = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("LlmT"));
	LlmT->SetText(FText::FromString(TEXT("LLM: オフライン")));
	BtnToggleLlm->AddChild(LlmT);
	BtnToggleLlm->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickToggleLlm);
	MenuConfigBox->AddChildToVerticalBox(BtnToggleLlm);

	auto AddSmallRow = [&](const FString& A, const FString& B, const FString& C) {
		UButton* Ba = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), FName(*A));
		UTextBlock* Ta = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(*(A + TEXT("t"))));
		Ta->SetText(FText::FromString(B));
		Ba->AddChild(Ta);
		MenuConfigBox->AddChildToVerticalBox(Ba);
		if (C == TEXT("subp"))
		{
			Ba->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickSubjectPrev);
		}
		else if (C == TEXT("subn"))
		{
			Ba->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickSubjectNext);
		}
		else if (C == TEXT("gp"))
		{
			Ba->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickGradePrev);
		}
		else if (C == TEXT("gn"))
		{
			Ba->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickGradeNext);
		}
		else if (C == TEXT("dp"))
		{
			Ba->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickDiffPrev);
		}
		else if (C == TEXT("dn"))
		{
			Ba->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickDiffNext);
		}
	};
	AddSmallRow(TEXT("BSubP"), TEXT("教科 ←"), TEXT("subp"));
	AddSmallRow(TEXT("BSubN"), TEXT("教科 →"), TEXT("subn"));
	AddSmallRow(TEXT("BGrP"), TEXT("学年 ←"), TEXT("gp"));
	AddSmallRow(TEXT("BGrN"), TEXT("学年 →"), TEXT("gn"));
	AddSmallRow(TEXT("BDfP"), TEXT("難易度 ←"), TEXT("dp"));
	AddSmallRow(TEXT("BDfN"), TEXT("難易度 →"), TEXT("dn"));

	BtnStart = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("BtnStart"));
	UTextBlock* St = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("St"));
	St->SetText(FText::FromString(TEXT("ゲーム開始")));
	BtnStart->AddChild(St);
	BtnStart->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickStart);
	MenuConfigBox->AddChildToVerticalBox(BtnStart);

	BtnBack = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("BtnBack"));
	UTextBlock* Bt = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Bt"));
	Bt->SetText(FText::FromString(TEXT("モード選択に戻る")));
	BtnBack->AddChild(Bt);
	BtnBack->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickBackMode);
	MenuConfigBox->AddChildToVerticalBox(BtnBack);
	Root->AddChildToVerticalBox(MenuConfigBox);

	TxtQuestion = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Q"));
	TxtQuestion->SetAutoWrapText(true);
	Root->AddChildToVerticalBox(TxtQuestion);

	TxtChoices = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("C"));
	TxtChoices->SetAutoWrapText(true);
	Root->AddChildToVerticalBox(TxtChoices);

	TxtMessage = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("M"));
	TxtMessage->SetAutoWrapText(true);
	Root->AddChildToVerticalBox(TxtMessage);

	RatingBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("Rating"));
	BtnRateGood = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("RG"));
	UTextBlock* Rg = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Rgt"));
	Rg->SetText(FText::FromString(TEXT("良い問題")));
	BtnRateGood->AddChild(Rg);
	BtnRateGood->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickRateGood);
	RatingBox->AddChildToVerticalBox(BtnRateGood);
	BtnRateBad = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), TEXT("RB"));
	UTextBlock* Rb = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Rbt"));
	Rb->SetText(FText::FromString(TEXT("悪い問題")));
	BtnRateBad->AddChild(Rb);
	BtnRateBad->OnClicked.AddDynamic(this, &UQuizMainWidget::OnClickRateBad);
	RatingBox->AddChildToVerticalBox(BtnRateBad);
	Root->AddChildToVerticalBox(RatingBox);
}

void UQuizMainWidget::NativeTick(const FGeometry& MyGeometry, const float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	APlayerController* PC = GetOwningPlayer();
	if (!PC)
	{
		return;
	}
	AAIQuizGameState* GS = PC->GetWorld()->GetGameState<AAIQuizGameState>();
	if (!GS)
	{
		return;
	}
	TxtStatus->SetText(FText::FromString(GS->GetStatusText()));
	const FString Gs = GS->GetUiGameState();
	const FString Step = GS->GetMenuStep();
	const bool bMenu = (Gs == QuizConst::StateMenu);
	MenuModeBox->SetVisibility(bMenu && Step == QuizConst::MenuStepMode ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	MenuConfigBox->SetVisibility(bMenu && Step == QuizConst::MenuStepConfig ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	const bool bPlayHud = (Gs == QuizConst::StatePlaying || Gs == QuizConst::StatePreloading || Gs == QuizConst::StateCorrect);
	TxtQuestion->SetVisibility(bPlayHud ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	TxtChoices->SetVisibility(bPlayHud ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	if (bPlayHud && GS->GetCurrentQuiz().IsValidItem())
	{
		const FQuizItem& Q = GS->GetCurrentQuiz();
		TxtQuestion->SetText(FText::FromString(FString::Printf(TEXT("Q: %s"), *Q.Question)));
		TxtChoices->SetText(FText::FromString(FString::Printf(TEXT("左: %s\n右: %s"), *Q.Choice0, *Q.Choice1)));
	}
	else
	{
		TxtQuestion->SetText(FText::GetEmpty());
		TxtChoices->SetText(FText::GetEmpty());
	}
	const bool bMsg = !GS->GetMessageText().IsEmpty();
	TxtMessage->SetVisibility(bMsg ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	TxtMessage->SetText(FText::FromString(GS->GetMessageText()));
	const bool bRate = (Gs == QuizConst::StateGameOver || Gs == QuizConst::StateClear);
	RatingBox->SetVisibility(bRate ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	if (BtnToggleLlm)
	{
		UTextBlock* Tb = Cast<UTextBlock>(BtnToggleLlm->GetChildAt(0));
		if (Tb)
		{
			Tb->SetText(FText::FromString(GS->IsLlmOnlineUi() ? TEXT("LLM: オンライン") : TEXT("LLM: オフライン")));
		}
	}
}

static AAIQuizGameState* QuizGetGameState(UQuizMainWidget* W)
{
	if (!W)
	{
		return nullptr;
	}
	APlayerController* PC = W->GetOwningPlayer();
	return PC && PC->GetWorld() ? PC->GetWorld()->GetGameState<AAIQuizGameState>() : nullptr;
}

void UQuizMainWidget::OnClickModeTen()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuSelectModeTen();
	}
}

void UQuizMainWidget::OnClickModeEndless()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuSelectModeEndless();
	}
}

void UQuizMainWidget::OnClickToggleLlm()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuToggleLlmOnline();
	}
}

void UQuizMainWidget::OnClickSubjectPrev()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuCycleSubject(-1);
	}
}

void UQuizMainWidget::OnClickSubjectNext()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuCycleSubject(1);
	}
}

void UQuizMainWidget::OnClickGradePrev()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuCycleGrade(-1);
	}
}

void UQuizMainWidget::OnClickGradeNext()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuCycleGrade(1);
	}
}

void UQuizMainWidget::OnClickDiffPrev()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuCycleDifficulty(-1);
	}
}

void UQuizMainWidget::OnClickDiffNext()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuCycleDifficulty(1);
	}
}

void UQuizMainWidget::OnClickStart()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->MenuStartGame();
	}
}

void UQuizMainWidget::OnClickBackMode()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->RequestBackToModeSelect();
	}
}

void UQuizMainWidget::OnClickRateGood()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->HudClickRatingGood();
	}
}

void UQuizMainWidget::OnClickRateBad()
{
	if (AAIQuizGameState* GS = QuizGetGameState(this))
	{
		GS->HudClickRatingBad();
	}
}
