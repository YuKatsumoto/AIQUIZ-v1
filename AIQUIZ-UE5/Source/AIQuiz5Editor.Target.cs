using UnrealBuildTool;
using System.Collections.Generic;

public class AIQuiz5EditorTarget : TargetRules
{
	public AIQuiz5EditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
		ExtraModuleNames.AddRange(new string[] { "AIQuiz5" });
	}
}
