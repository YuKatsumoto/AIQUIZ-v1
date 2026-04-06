"""
オフライン問題バンクの品質管理スクリプト

機能:
  1. 完全重複の検出・削除
  2. 類似問題（数値だけ違うテンプレ重複）の検出・削除
  3. 誤答チェック（正解インデックスの範囲外、空の選択肢、問題文が空など）
  4. レポート出力 + クリーニング済みバンクの書き出し

使い方:
  python tools/qa_audit.py                   # レポートのみ（ドライラン）
  python tools/qa_audit.py --fix             # 問題を自動修正してバンクを上書き保存
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any


BANK_PATH = Path(__file__).resolve().parent.parent / "offline_bank.json"


# ─── 類似度ユーティリティ ───────────────────────────

def _normalize(q: str) -> str:
    """空白除去して小文字化"""
    return re.sub(r"\s+", "", (q or "")).lower()


def _pattern_key(q: str) -> str:
    """数値を # に置換してテンプレートキーを作る"""
    s = _normalize(q)
    s = re.sub(r"\d+", "#", s)
    s = re.sub(r"[、。,.!?！？]", "", s)
    return s


def _bigram_set(s: str) -> set[str]:
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ─── バリデーション ─────────────────────────────────

class Issue:
    def __init__(self, subject: str, grade: str, index: int, kind: str, detail: str, quiz: dict):
        self.subject = subject
        self.grade = grade
        self.index = index
        self.kind = kind
        self.detail = detail
        self.quiz = quiz

    def __str__(self):
        q_short = str(self.quiz.get("q", ""))[:50]
        return f"[{self.kind}] {self.subject}/{self.grade} #{self.index}: {self.detail} | q=\"{q_short}\""


def validate_single(quiz: dict, subject: str, grade: str, index: int) -> list[Issue]:
    """1問ごとのバリデーション"""
    issues: list[Issue] = []
    q = str(quiz.get("q", "")).strip()
    c = quiz.get("c", [])
    a = quiz.get("a", None)

    # 問題文が空
    if not q:
        issues.append(Issue(subject, grade, index, "EMPTY_Q", "問題文が空です", quiz))

    # 選択肢がリストでない / 数が不正
    if not isinstance(c, list) or len(c) not in (2, 4):
        issues.append(Issue(subject, grade, index, "BAD_CHOICES", f"選択肢の数が不正: {len(c) if isinstance(c, list) else 'not a list'}", quiz))
        return issues  # これ以上チェック不可

    # 空の選択肢
    for ci, choice in enumerate(c):
        if not str(choice).strip():
            issues.append(Issue(subject, grade, index, "EMPTY_CHOICE", f"選択肢[{ci}]が空です", quiz))

    # 正解インデックスが不正
    if a is None:
        issues.append(Issue(subject, grade, index, "NO_ANSWER", "正解インデックス(a)がありません", quiz))
    else:
        try:
            ai = int(a)
            if ai < 0 or ai >= len(c):
                issues.append(Issue(subject, grade, index, "ANSWER_OOB", f"正解インデックス {ai} が範囲外 (0~{len(c)-1})", quiz))
        except (ValueError, TypeError):
            issues.append(Issue(subject, grade, index, "BAD_ANSWER", f"正解インデックスが数値でない: {a!r}", quiz))

    # 選択肢が全て同じ
    cleaned = [str(x).strip() for x in c]
    if len(set(cleaned)) == 1:
        issues.append(Issue(subject, grade, index, "ALL_SAME", "全ての選択肢が同じテキストです", quiz))

    # 重複する選択肢
    elif len(set(cleaned)) < len(cleaned):
        issues.append(Issue(subject, grade, index, "DUP_CHOICE", "選択肢に重複があります", quiz))

    return issues


def find_duplicates(quizzes: list[dict], subject: str, grade: str) -> tuple[list[Issue], set[int]]:
    """完全重複と類似重複を検出し、削除候補indexのセットを返す"""
    issues: list[Issue] = []
    remove_indices: set[int] = set()

    # 完全重複: 同じ問題文
    seen_exact: dict[str, int] = {}
    for i, q in enumerate(quizzes):
        qt = _normalize(q.get("q", ""))
        if qt in seen_exact:
            issues.append(Issue(subject, grade, i, "EXACT_DUP", f"#{seen_exact[qt]}と完全重複", q))
            remove_indices.add(i)
        else:
            seen_exact[qt] = i

    # テンプレート重複: 数値を置換したパターンが同一
    seen_pattern: dict[str, list[int]] = defaultdict(list)
    for i, q in enumerate(quizzes):
        if i in remove_indices:
            continue
        pat = _pattern_key(q.get("q", ""))
        if pat:
            seen_pattern[pat].append(i)

    for pat, indices in seen_pattern.items():
        if len(indices) > 8:
            # 同一テンプレート9問目以降を削除候補（8問までは許容）
            for idx in indices[8:]:
                issues.append(Issue(subject, grade, idx, "TEMPLATE_DUP", f"テンプレート重複 (同パターン{len(indices)}問中の余剰)", quizzes[idx]))
                remove_indices.add(idx)

    return issues, remove_indices


# ─── メイン処理 ──────────────────────────────────────

def audit(bank_path: Path, fix: bool = False) -> dict[str, Any]:
    with open(bank_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_issues: list[Issue] = []
    stats = {
        "total_before": 0,
        "total_after": 0,
        "removed_exact_dup": 0,
        "removed_template_dup": 0,
        "removed_bad": 0,
        "issues_by_kind": defaultdict(int),
    }

    cleaned_data: dict = {}

    for subject in data:
        cleaned_data[subject] = {}
        for grade in data[subject]:
            quizzes = data[subject][grade]
            stats["total_before"] += len(quizzes)

            # 1) 個別バリデーション
            bad_indices: set[int] = set()
            for i, q in enumerate(quizzes):
                issues = validate_single(q, subject, grade, i)
                for issue in issues:
                    all_issues.append(issue)
                    stats["issues_by_kind"][issue.kind] += 1
                # 致命的な問題は削除対象
                fatal_kinds = {"EMPTY_Q", "BAD_CHOICES", "NO_ANSWER", "ANSWER_OOB", "BAD_ANSWER", "ALL_SAME"}
                if any(iss.kind in fatal_kinds for iss in issues):
                    bad_indices.add(i)

            # 2) 重複検出
            dup_issues, dup_indices = find_duplicates(quizzes, subject, grade)
            for issue in dup_issues:
                all_issues.append(issue)
                stats["issues_by_kind"][issue.kind] += 1

            # 3) クリーニング
            remove_set = bad_indices | dup_indices
            cleaned = [q for i, q in enumerate(quizzes) if i not in remove_set]
            cleaned_data[subject][grade] = cleaned
            stats["total_after"] += len(cleaned)
            stats["removed_exact_dup"] += sum(1 for i in dup_indices if any(iss.index == i and iss.kind == "EXACT_DUP" for iss in dup_issues))
            stats["removed_template_dup"] += sum(1 for i in dup_indices if any(iss.index == i and iss.kind == "TEMPLATE_DUP" for iss in dup_issues))
            stats["removed_bad"] += len(bad_indices)

    # ─── レポート出力 ───
    print("=" * 60)
    print("  オフライン問題バンク 品質管理レポート")
    print("=" * 60)
    print(f"  問題総数 (修正前): {stats['total_before']}")
    print(f"  問題総数 (修正後): {stats['total_after']}")
    print(f"  削除数:            {stats['total_before'] - stats['total_after']}")
    print(f"    - 完全重複:      {stats['removed_exact_dup']}")
    print(f"    - テンプレ重複:  {stats['removed_template_dup']}")
    print(f"    - 不正な問題:    {stats['removed_bad']}")
    print()
    print("  検出された問題:")
    for kind, count in sorted(stats["issues_by_kind"].items()):
        print(f"    {kind}: {count}件")
    print()

    # 科目・学年ごとの内訳
    print("  科目・学年別 問題数:")
    for subject in cleaned_data:
        for grade in cleaned_data[subject]:
            orig = len(data[subject][grade])
            clean = len(cleaned_data[subject][grade])
            diff = orig - clean
            mark = f" (-{diff})" if diff > 0 else ""
            print(f"    {subject}/{grade}: {orig} → {clean}{mark}")
    print()

    if all_issues:
        print("  詳細 (最大30件):")
        for iss in all_issues[:30]:
            print(f"    {iss}")
        if len(all_issues) > 30:
            print(f"    ... 他 {len(all_issues) - 30}件")
    print()

    if fix:
        # バックアップを作成
        backup_path = bank_path.with_suffix(".backup.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  バックアップを作成: {backup_path}")

        # クリーニング済みデータを書き出し
        with open(bank_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        print(f"  クリーニング済みバンクを保存: {bank_path}")
        print(f"  {stats['total_before'] - stats['total_after']}問を削除しました。")
    else:
        print("  ドライラン: 変更は保存されていません。")
        print("  修正を適用するには --fix オプションを付けて実行してください。")

    print("=" * 60)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="オフライン問題バンク品質管理")
    parser.add_argument("--fix", action="store_true", help="問題を自動修正してバンクを上書き保存")
    parser.add_argument("--bank", type=str, default=str(BANK_PATH), help="問題バンクのパス")
    args = parser.parse_args()
    audit(Path(args.bank), fix=args.fix)
