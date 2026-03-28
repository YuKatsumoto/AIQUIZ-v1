import tempfile
import time
import unittest
from pathlib import Path

from game.core.constants import MODE_ENDLESS, MODE_TEN
from game.core.providers.buffered_provider import BufferedQuizProvider
from game.core.quiz_provider import OfflineQuizProvider, QuizItem


class BufferedProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.ratings = base / "quiz_ratings.json"
        self.ratings.write_text('{"good":[],"bad":[]}', encoding="utf-8")
        self.reject_log = base / "reject.jsonl"
        self.source_log = base / "source.jsonl"
        bank = {
            "算数": {
                "3": [
                    {"q": "1+1?", "c": ["2", "3"], "a": 0, "e": "2"},
                    {"q": "2+2?", "c": ["4", "5"], "a": 0, "e": "4"},
                    {"q": "3+3?", "c": ["6", "7"], "a": 0, "e": "6"},
                ]
            }
        }
        self.bank_path = base / "offline_bank.json"
        self.bank_path.write_text(__import__("json").dumps(bank, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_buffered_provider_prefills_and_pulls(self):
        offline = OfflineQuizProvider(str(self.bank_path))
        provider = BufferedQuizProvider(
            offline_provider=offline,
            ratings_path=str(self.ratings),
            reject_log_path=str(self.reject_log),
            source_log_path=str(self.source_log),
            num_workers=1,
        )
        try:
            provider.set_llm_mode("OFFLINE")
            provider.begin_round("算数", 3, "普通", MODE_TEN, 10)
            for _ in range(40):
                if provider.buffered_count() > 0:
                    break
                time.sleep(0.02)
            got = provider.get_quizzes("算数", 3, "普通", MODE_TEN, 2)
            self.assertGreaterEqual(len(got), 1)
        finally:
            provider.stop()

    def test_endless_mode_ready(self):
        offline = OfflineQuizProvider(str(self.bank_path))
        provider = BufferedQuizProvider(
            offline_provider=offline,
            ratings_path=str(self.ratings),
            reject_log_path=str(self.reject_log),
            source_log_path=str(self.source_log),
            num_workers=1,
        )
        try:
            provider.begin_round("算数", 3, "普通", MODE_ENDLESS, 1)
            for _ in range(40):
                if provider.is_ready_for_mode():
                    break
                time.sleep(0.02)
            self.assertTrue(provider.is_ready_for_mode())
        finally:
            provider.stop()

    def test_online_failure_falls_back_to_offline(self):
        offline = OfflineQuizProvider(str(self.bank_path))
        provider = BufferedQuizProvider(
            offline_provider=offline,
            ratings_path=str(self.ratings),
            reject_log_path=str(self.reject_log),
            source_log_path=str(self.source_log),
            num_workers=1,
        )
        try:
            provider.set_llm_mode("ONLINE")
            provider._fetch_online = lambda count: []  # force online miss
            provider.begin_round("算数", 3, "普通", MODE_TEN, 10)
            for _ in range(50):
                if provider.buffered_count() > 0:
                    break
                time.sleep(0.02)
            got = provider.get_quizzes("算数", 3, "普通", MODE_TEN, 1)
            self.assertGreaterEqual(len(got), 1)
        finally:
            provider.stop()

    def test_mark_bad_and_good_rating_saved(self):
        offline = OfflineQuizProvider(str(self.bank_path))
        provider = BufferedQuizProvider(
            offline_provider=offline,
            ratings_path=str(self.ratings),
            reject_log_path=str(self.reject_log),
            source_log_path=str(self.source_log),
            num_workers=1,
        )
        try:
            quiz = QuizItem(q="テスト問題", c=["A", "B"], a=0, e="", src="TEST")
            provider.mark_quiz_good(quiz, subject="算数", grade=3, difficulty="普通")
            provider.mark_quiz_bad(quiz, subject="算数", grade=3, difficulty="普通")
            data = __import__("json").loads(self.ratings.read_text(encoding="utf-8"))
            good_qs = {x.get("q") for x in data.get("good", []) if isinstance(x, dict)}
            bad_qs = {x.get("q") for x in data.get("bad", []) if isinstance(x, dict)}
            self.assertIn("テスト問題", good_qs)
            self.assertIn("テスト問題", bad_qs)
        finally:
            provider.stop()


if __name__ == "__main__":
    unittest.main()
