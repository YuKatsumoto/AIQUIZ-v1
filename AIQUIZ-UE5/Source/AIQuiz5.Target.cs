using UnrealBuildTool;
using System.Collections.Generic;

public class AIQuiz5Target : TargetRules
{
	public AIQuiz5Target(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
		ExtraModuleNames.AddRange(new string[] { "AIQuiz5" });
	}
}
