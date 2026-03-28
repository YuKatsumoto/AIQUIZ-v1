import json
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from .constants import MODE_TEN


@dataclass
class QuizItem:
    q: str
    c: List[str]
    a: int
    e: str = ""
    src: str = "OFFLINE"
    img: str = ""
    choice_img: List[str] | None = None


class QuizProvider(Protocol):
    def get_quizzes(
        self, subject: str, grade: int, difficulty: str, mode: str, count: int
    ) -> List[QuizItem]:
        ...

    def begin_round(self, subject: str, grade: int, difficulty: str, mode: str, target_count: int) -> None:
        ...

    def stop(self) -> None:
        ...

    def submit_result(self, quiz: Optional[QuizItem], correct: bool) -> None:
        ...


class OfflineQuizProvider:
    def __init__(self, bank_path: str):
        self.bank_path = bank_path
        self.bank = self._load_bank()

    def begin_round(self, subject: str, grade: int, difficulty: str, mode: str, target_count: int) -> None:
        return None

    def stop(self) -> None:
        return None

    def submit_result(self, quiz: Optional[QuizItem], correct: bool) -> None:
        return None

    def _load_bank(self) -> Dict:
        try:
            with open(self.bank_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"[bank load error] {e}")
        return {}

    def _normalize(self, raw: Dict) -> Optional[QuizItem]:
        if not isinstance(raw, dict):
            return None
        q = str(raw.get("q", "")).strip()
        c = raw.get("c", [])
        a = raw.get("a", None)
        if not q or not isinstance(c, list) or len(c) != 2:
            return None
        try:
            a_int = int(a)
        except Exception:
            return None
        if a_int not in (0, 1):
            return None
        e = str(raw.get("e", raw.get("exp", ""))).strip()
        src = str(raw.get("src", "OFFLINE")).strip() or "OFFLINE"
        c0 = str(c[0]).strip()
        c1 = str(c[1]).strip()
        if not c0 or not c1:
            return None
        img = str(raw.get("img", "")).strip()
        choice_img = raw.get("choice_img", raw.get("choiceImg", []))
        if not isinstance(choice_img, list):
            choice_img = []
        return QuizItem(q=q, c=[c0, c1], a=a_int, e=e, src=src, img=img, choice_img=[str(x) for x in choice_img])

    def _complexity_score(self, item: QuizItem, subject: str, grade: int) -> float:
        text = f"{item.q} {' '.join(item.c)} {item.e}"
        q_text = item.q

        score = 0.0
        score += len(q_text) / 40.0
        score += len(item.e) / 80.0
        score += len(re.findall(r"\d", text)) * 0.08
        score += len(re.findall(r"[\+\-\*/÷×%]", text)) * 0.25
        score += len(re.findall(r"[()（）]", text)) * 0.2

        if "【応用】" in q_text:
            score += 1.2
        if "【基本】" in q_text:
            score -= 0.6

        if subject == "算数":
            for token in ["割合", "比", "速さ", "体積", "平均", "合同", "比例", "反比例"]:
                if token in text:
                    score += 0.9
            if re.search(r"\d{3,}", text):
                score += 0.4
        elif subject == "理科":
            for token in ["実験", "観察", "原因", "結果", "規則", "電磁石", "水溶液", "燃焼", "光合成"]:
                if token in text:
                    score += 0.7
        elif subject == "国語":
            for token in ["敬語", "四字熟語", "古典", "短歌", "俳句", "歴史的仮名遣い", "比喩"]:
                if token in text:
                    score += 0.9

        score -= max(0, grade - 1) * 0.08
        return score

    def _bucket_by_difficulty(
        self, items: List[QuizItem], subject: str, grade: int, difficulty: str
    ) -> List[QuizItem]:
        if len(items) <= 2:
            return items

        scored = sorted(
            [(self._complexity_score(it, subject, grade), it) for it in items],
            key=lambda x: x[0],
        )
        n = len(scored)
        low_end = max(1, n // 3)
        high_start = max(low_end, (2 * n) // 3)

        if difficulty == "簡単":
            bucket = [it for _, it in scored[:low_end]]
        elif difficulty == "難しい":
            bucket = [it for _, it in scored[high_start:]]
        else:
            bucket = [it for _, it in scored[low_end:high_start]]

        return bucket if bucket else items

    def _fallback_question(self, subject: str, grade: int) -> QuizItem:
        a = random.randint(2, 20)
        b = random.randint(1, 10)
        ans = a + b
        wrong = ans + random.choice([-2, -1, 1, 2])
        choices = [str(ans), str(wrong)]
        random.shuffle(choices)
        return QuizItem(
            q=f"[{subject}{grade}年] {a}+{b} はどちら？",
            c=choices,
            a=choices.index(str(ans)),
            e=f"{a}+{b}={ans}",
            src="FALLBACK",
            img="",
            choice_img=[],
        )

    def get_quizzes(
        self, subject: str, grade: int, difficulty: str, mode: str, count: int
    ) -> List[QuizItem]:
        grade_str = str(grade)
        raw_items = self.bank.get(subject, {}).get(grade_str, [])
        items: List[QuizItem] = []
        for raw in raw_items:
            n = self._normalize(raw)
            if n:
                items.append(n)

        if not items:
            if mode == MODE_TEN:
                return [self._fallback_question(subject, grade) for _ in range(max(1, count))]
            return [self._fallback_question(subject, grade)]

        pool = self._bucket_by_difficulty(items, subject, grade, difficulty)
        random.shuffle(pool)

        if mode == MODE_TEN:
            uniq = []
            seen = set()
            for q in pool + items:
                if q.q in seen:
                    continue
                seen.add(q.q)
                uniq.append(q)
                if len(uniq) >= count:
                    break
            while len(uniq) < count:
                uniq.append(self._fallback_question(subject, grade))
            return uniq

        return [random.choice(pool)]


# ========= 2D parity prompt helpers (ONLINE generation) =========
# These tables/lines are ported from 2D_pygame.py (1115-1490) to keep quiz generation
# consistent across 2D and 3D versions.

QUESTION_TYPES: dict[str, dict[int, list[str]]] = {
    "算数": {
        1: ["足し算", "引き算", "時計の読み方", "図形", "長さ比べ", "数の数え方"],
        2: ["九九", "長さの単位(cm, m)", "かさ(L, dL)", "時刻と時間", "筆算", "簡単な分数"],
        3: ["割り算", "小数", "分数", "円と球", "重さ(g, kg)", "表とグラフ"],
        4: ["面積", "角度", "大きな数", "小数の計算", "分数の計算", "立方体と直方体"],
        5: ["割合", "小数の掛け算・割り算", "分数の足し算・引き算", "体積", "平均", "合同な図形"],
        6: ["比", "分数の掛け算・割り算", "速さ", "比例と反比例", "立体の体積", "データの活用"],
    },
    "理科": {
        1: ["身近な植物", "身近な生き物", "季節の草花", "虫", "どんぐりなどの木の実"],
        2: ["野菜の育ち方", "ダンゴムシなどの虫", "季節の生き物", "天気", "おもちゃの仕組み"],
        3: ["磁石の性質", "電気の通り道", "昆虫の体のつくり", "植物の育ち方", "太陽と影", "物の重さ"],
        4: ["星と星座", "月の動き", "季節と生き物", "人の体のつくり(骨と筋肉)", "空気と水の性質", "乾電池と豆電球"],
        5: ["メダカの誕生", "植物の発芽と成長", "天気の変化", "振り子の動き", "電磁石の性質", "流れる水の働き"],
        6: ["人体のつくりと働き(呼吸・血液など)", "植物の養分(光合成)", "水溶液の性質", "物の燃え方", "てこの規則性", "地球と環境"],
    },
    "国語": {
        1: ["ひらがな", "カタカナ", "簡単な漢字", "物の名前", "挨拶の言葉", "数え方"],
        2: ["漢字の読み書き", "反対の意味の言葉", "似た意味の言葉", "主語と述語", "様子を表す言葉"],
        3: ["ローマ字", "ことわざ", "部首", "国語辞典の使い方", "修飾語", "送り仮名"],
        4: ["慣用句", "敬語の基本", "つなぎ言葉(接続語)", "熟語の構成", "漢字の部首と意味"],
        5: ["敬語(尊敬語・謙譲語・丁寧語)", "四字熟語", "同音異義語", "古典(竹取物語など)", "類義語と対義語"],
        6: ["座右の銘", "短歌・俳句", "歴史的仮名遣い", "難しい熟語", "表現の工夫(比喩など)", "言葉の由来"],
    },
}

GRADE_SCOPE_GUIDES: dict[str, dict[int, dict[str, str]]] = {
    "算数": {
        1: {"must": "20までのたし算・ひき算、数の大小、簡単な時計や図形", "avoid": "分数・小数・割合・速さ・体積のような上級内容"},
        2: {"must": "九九、長さ・かさ、時刻、簡単な表の読み取り", "avoid": "割合・速さ・体積・比のような高学年中心の内容"},
        3: {"must": "かけ算、わり算、分数の入口、円と球、長さ・重さ", "avoid": "割合・比・複雑な速さや高難度の面積問題"},
        4: {"must": "大きな数、面積、角、折れ線グラフ、小数・分数", "avoid": "比や高度な割合など高学年中心の内容"},
        5: {"must": "小数と分数の計算、割合、平均、単位量あたり、体積、図形の性質", "avoid": "中学レベルの方程式や座標"},
        6: {"must": "比、割合、速さ、拡大図と縮図、円の面積、資料の見方、複数段階の判断", "avoid": "低学年向けの一桁計算や単純な個数計算だけの問題"},
    },
    "理科": {
        3: {"must": "植物やこん虫、光、音、磁石、電気など身近な観察内容", "avoid": "人体のしくみや水よう液など高学年中心の内容"},
        4: {"must": "電流、天気、月や星、温度、金属や空気と水の変化", "avoid": "消化や血液循環、地層など6年寄りの内容"},
        5: {"must": "発芽と成長、流れる水、天気、ふりこ、てこ、電磁石、ものの溶け方", "avoid": "中学理科レベルの化学式や専門用語"},
        6: {"must": "人体、水よう液、月と太陽、土地のつくり、てこ、発電や電気の利用", "avoid": "中学以降の専門計算や抽象理論"},
    },
    "国語": {
        1: {"must": "ひらがな、かたかな、やさしい言葉、短い文の読解", "avoid": "敬語や抽象的な文法用語"},
        2: {"must": "語彙、短文読解、主語と述語の入口、漢字の基本", "avoid": "高度な敬語や長文要旨問題"},
        3: {"must": "漢字、ことわざ・慣用句の入口、段落の読み取り、修飾語の基本", "avoid": "難しい敬語運用や抽象的な評論読解"},
        4: {"must": "文法の基本、漢字、要点把握、段落や接続の理解", "avoid": "中学寄りの古典文法や難解な評論"},
        5: {"must": "敬語、文の組み立て、熟語、資料や文章の読み取り、理由説明", "avoid": "低学年向けの単純な語句暗記だけの問題"},
        6: {"must": "敬語、表現の効果、文章構成、要旨把握、漢字や語句の使い分け", "avoid": "低学年向けの単純な読みだけの問題"},
    },
}

SCIENCE_GRADE_KEYWORDS: dict[int, list[str]] = {
    3: ["植物", "昆虫", "チョウ", "ゴム", "風", "光", "音", "磁石", "電気", "日なた", "日かげ"],
    4: ["電流", "乾電池", "直列", "並列", "天気", "月", "星", "空気", "水", "温度", "金属"],
    5: ["発芽", "受粉", "流れる水", "天気の変化", "ふりこ", "てこ", "電磁石", "ものの溶け方"],
    6: ["消化", "呼吸", "血液", "水よう液", "月と太陽", "地層", "火山", "発電", "電気の利用", "てこ"],
}

JAPANESE_GRADE_KEYWORDS: dict[int, list[str]] = {
    1: ["ひらがな", "カタカナ", "ことば", "文", "漢字"],
    2: ["漢字", "主語", "述語", "ことば", "文しょう"],
    3: ["漢字", "ことわざ", "慣用句", "段落", "修飾語", "こそあど"],
    4: ["漢字", "段落", "要点", "接続語", "修飾語", "文法"],
    5: ["敬語", "熟語", "主語", "述語", "修飾語", "要旨", "段落", "資料", "理由", "文脈"],
    6: ["敬語", "要旨", "文章構成", "表現", "熟語", "漢字", "理由", "文脈", "心情", "筆者"],
}

SUBJECT_GRADE_RECOMMENDED_DIFFICULTY: dict[str, dict[int, str]] = {
    "算数": {1: "簡単", 2: "簡単", 3: "普通", 4: "普通", 5: "難しい", 6: "難しい"},
    "理科": {1: "簡単", 2: "簡単", 3: "普通", 4: "普通", 5: "難しい", 6: "難しい"},
    "国語": {1: "簡単", 2: "簡単", 3: "普通", 4: "普通", 5: "普通", 6: "難しい"},
}

DIFFICULTY_LEVELS = ["簡単", "普通", "難しい"]


def _difficulty_index(difficulty: str) -> int:
    try:
        return DIFFICULTY_LEVELS.index(str(difficulty))
    except Exception:
        return 1


def _safe_grade_int(grade: int, default: int = 3) -> int:
    try:
        return max(1, min(6, int(grade)))
    except Exception:
        return default


def recommended_difficulty(subject: str, grade: int) -> str:
    g_int = _safe_grade_int(grade, default=3)
    subject_table = SUBJECT_GRADE_RECOMMENDED_DIFFICULTY.get(subject, {})
    if g_int in subject_table:
        return subject_table[g_int]
    if g_int <= 2:
        return "簡単"
    if g_int <= 4:
        return "普通"
    return "難しい"


def effective_difficulty(subject: str, grade: int, requested_difficulty: str) -> str:
    """
    2Dと同様に、学年・教科に対して不自然な難易度を避けるために補正。
    """
    g_int = _safe_grade_int(grade, default=3)
    req_idx = _difficulty_index(requested_difficulty)
    rec_idx = _difficulty_index(recommended_difficulty(subject, g_int))
    max_idx = len(DIFFICULTY_LEVELS) - 1

    min_allowed = max(0, rec_idx - 1)
    max_allowed = min(max_idx, rec_idx + 1)
    if g_int <= 2:
        max_allowed = min(max_allowed, 1)
    elif g_int >= 5:
        min_allowed = max(min_allowed, 1)

    eff_idx = min(max(req_idx, min_allowed), max_allowed)
    return DIFFICULTY_LEVELS[eff_idx]


def grade_scope_prompt_lines(grade: int, subject: str) -> list[str]:
    g_int = _safe_grade_int(grade, default=3)
    lines: list[str] = []

    allowed_topics = QUESTION_TYPES.get(subject, {}).get(g_int, [])
    if allowed_topics:
        lines.append(f"IMPORTANT: Allowed curriculum topics for this exact grade: {', '.join(allowed_topics)}.")
        lines.append("IMPORTANT: Every quiz must clearly belong to one of the allowed curriculum topics above.")

    guide = GRADE_SCOPE_GUIDES.get(subject, {}).get(g_int, {})
    must = str(guide.get("must", "")).strip()
    avoid = str(guide.get("avoid", "")).strip()
    if must:
        lines.append(f"IMPORTANT: Target this grade feel: {must}.")
    if avoid:
        lines.append(f"IMPORTANT: Avoid level mismatch such as: {avoid}.")

    if subject == "算数" and g_int >= 5:
        lines.append(
            "IMPORTANT: For upper-elementary math, avoid low-grade one-step word problems such as simple "
            "'1袋に5個、3袋で何個' patterns unless the question also requires ratio, percentage, speed, "
            "area, volume, graph reading, or multi-step reasoning."
        )
    if subject == "国語" and g_int >= 5:
        lines.append(
            "IMPORTANT: For grade 5-6 Japanese, prefer passage interpretation, grammar, kanji usage, "
            "敬語, or reasoning about wording over very short single-word meaning drills."
        )
    if subject == "理科" and g_int >= 5:
        lines.append(
            "IMPORTANT: For grade 5-6 science, prefer observation, experiment, comparison, explanation of "
            "cause/effect, or curriculum concepts over simple fact recall only."
        )
    return lines


def grade_fit_prompt_lines(grade: int, subject: str, difficulty: str) -> list[str]:
    idx = _difficulty_index(difficulty)
    lines = [
        "IMPORTANT: Match the requested grade and subject exactly. Do not downgrade to lower-grade content.",
        "IMPORTANT: Use age-appropriate terms, units, and curriculum-style phrasing for the specified grade.",
    ]

    if idx == 1:
        lines.extend(
            [
                "For NORMAL difficulty, generate textbook-middle level questions for that grade (not introductory or review-only lower-grade questions).",
                "For NORMAL difficulty, include at least one reasoning step (comparison, interpretation, calculation, or cause/effect), not pure recall only.",
                "Make wrong choices plausible for students of that grade and subject.",
            ]
        )
        if grade >= 3:
            lines.append("If grade >= 3, avoid overly easy lower-grade items such as obvious single-step one-digit arithmetic or simple word guessing.")
        if grade >= 5:
            lines.append("If grade >= 5, prefer questions requiring organizing information, intermediate steps, or checking evidence/reasoning.")
    elif idx == 2:
        lines.extend(
            [
                "For HARD difficulty, stay within grade scope but use application-oriented or multi-step questions.",
                "Combine multiple learned points from the same grade when possible.",
            ]
        )
    else:
        lines.append("For EASY difficulty, keep it basic but still within the specified grade and subject scope.")

    return lines


def build_online_prompt_2d_style(
    subject: str,
    grade: int,
    difficulty: str,
    count: int,
    history: list[str] | None = None,
    good_examples: list[dict] | None = None,
    bad_examples: list[dict] | None = None,
) -> str:
    """
    2Dの `_base_prompt` / `_grade_fit_prompt_lines` / `_grade_scope_prompt_lines` 相当を3D向けにまとめたもの。
    3Dではバッチ生成数は呼び出し側(count)で決める（JSONのみ返す）。
    """
    history = history or []
    good_examples = good_examples or []
    bad_examples = bad_examples or []

    g_int = _safe_grade_int(grade, default=3)
    eff_diff = effective_difficulty(subject, g_int, difficulty)

    # トピックをランダムに選択して出題の幅を広げる（2D準拠）
    topics = QUESTION_TYPES.get(subject, {}).get(g_int, ["一般"])
    topic = random.choice(topics)
    topic_batch = list(topics)
    if len(topic_batch) > max(2, min(6, int(count))):
        topic_batch = random.sample(topic_batch, max(2, min(6, int(count))))

    example = [
        {"q": "問題文1", "c": ["選択肢A", "選択肢B"], "a": 0, "e": "解説1"},
        {"q": "問題文2", "c": ["選択肢C", "選択肢D"], "a": 1, "e": "解説2"},
    ]
    example_json = json.dumps(example, ensure_ascii=False)

    diff_instruction = ""
    if eff_diff == "簡単":
        diff_instruction = "・基礎的な知識を問う問題にしてください。\n・ひねりは加えず、ストレートな問題にしてください。"
    elif eff_diff == "難しい":
        diff_instruction = "・応用力や思考力を問う少し難しい問題にしてください。\n・引っかけ問題や、複数のステップを要する問題を含めても構いません。"
    else:
        diff_instruction = "・標準的なレベルの問題にしてください。\n・教科書の練習問題レベルを意識してください。"

    lines: list[str] = [
        f"日本の小学校{g_int}年生向け、{subject}の『{topic}』に関する二択クイズを作成してください。",
        f"難易度設定: {eff_diff}",
        diff_instruction,
        "ルール1: 問題文に絵文字や記号を入れないこと",
        "ルール2: JSONの配列(List)形式のみ出力してください。選択肢は2つ。子供向けの言葉で。",
        f"例: {example_json}",
        f"IMPORTANT: Return exactly {max(1, int(count))} quiz objects in one JSON array.",
        "IMPORTANT: Output JSON only, with no markdown and no extra prose.",
        "IMPORTANT: Within one response, diversify sub-topics and avoid repeating the same unit-conversion pattern/template.",
        f"IMPORTANT: Candidate topics for this batch are: {', '.join(topic_batch)}.",
        "IMPORTANT: Spread the quizzes across different candidate topics when possible.",
    ]

    if subject == "国語" and g_int >= 5:
        lines.extend(
            [
                "IMPORTANT (Japanese grade 5-6): Avoid generating consecutive vocabulary-meaning items.",
                "When outputting multiple quizzes, each quiz must use a different sub-genre (reading comprehension, grammar, kanji/notation, vocabulary usage, honorific/polite forms).",
                "Do not output two questions in the same 'word meaning / phrase meaning' format in one response.",
            ]
        )

    lines.extend(grade_fit_prompt_lines(g_int, subject, eff_diff))
    lines.extend(grade_scope_prompt_lines(g_int, subject))

    if g_int in (1, 2):
        lines.insert(3, "特別ルール: 小学1・2年生向けなので、漢字は使わず「ひらがな」を多くしてください。")
        lines.insert(4, "特別ルール: 難しい言葉は使わず、子供がわかるやさしい言葉で書いてください。")

    # good/bad examples (2D準拠)
    scoped_good = [q for q in good_examples if isinstance(q, dict) and q.get("subject") == subject and str(q.get("grade")) == str(g_int)]
    if scoped_good:
        sample_q = random.choice(scoped_good)
        qtxt = str(sample_q.get("q", "")).strip()
        if qtxt:
            lines.append(f"※参考: 過去に高く評価された良問のテイストや難易度を参考にしてください -> Q:{qtxt}")

    if history:
        lines.append("※以下の問題とは内容・数値を必ず変えて作成してください:")
        for h in history[-20:]:
            if str(h).strip():
                lines.append(f"- {str(h).strip()}")

    scoped_bad = [
        b
        for b in bad_examples
        if isinstance(b, dict)
        and b.get("q")
        and (
            (str(b.get("subject", "")).strip() == subject and str(b.get("grade", "")).strip() == str(g_int))
            or (not str(b.get("subject", "")).strip() and not str(b.get("grade", "")).strip())
        )
    ]
    bad_pool = scoped_bad if scoped_bad else [b for b in bad_examples if isinstance(b, dict) and b.get("q")]
    if bad_pool:
        bad_samples = random.sample(bad_pool, min(3, len(bad_pool)))
        lines.append("※以下の問題は以前「悪い」と評価されたので、似た形式や内容の問題は絶対に出題しないでください:")
        for bq in bad_samples:
            lines.append(f"- {str(bq.get('q', '')).strip()}")

    return "\n".join([ln for ln in lines if str(ln).strip()])
