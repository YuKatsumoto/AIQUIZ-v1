import unittest

from game.core.constants import (
    MENU_STEP_CONFIG,
    MENU_STEP_MODE,
    MODE_ENDLESS,
    MODE_TEN,
    STATE_CORRECT,
    STATE_GAME_OVER,
    STATE_PLAYING,
    STATE_PRELOADING,
)
from game.core.game_state import QuizGameState
from game.core.quiz_provider import QuizItem


class StubProvider:
    def __init__(self, answer=0):
        self.answer = answer
        self.good_called = 0
        self.bad_called = 0

    def get_quizzes(self, subject, grade, difficulty, mode, count):
        quiz = QuizItem(q="1+1?", c=["2", "3"], a=self.answer, e="1+1=2", src="TEST")
        if mode == MODE_TEN:
            return [quiz for _ in range(count)]
        return [quiz]

    def mark_quiz_good(self, quiz, subject, grade, difficulty=""):
        self.good_called += 1

    def mark_quiz_bad(self, quiz, subject, grade, difficulty=""):
        self.bad_called += 1


class EmptyThenReadyProvider:
    def __init__(self):
        self.calls = 0

    def get_quizzes(self, subject, grade, difficulty, mode, count):
        self.calls += 1
        if self.calls == 1:
            return []
        quiz = QuizItem(q="2+2?", c=["4", "5"], a=0, e="2+2=4", src="TEST")
        return [quiz for _ in range(count)]


class GameStateTests(unittest.TestCase):
    def test_start_game_enters_preloading_then_playing(self):
        gs = QuizGameState(provider=StubProvider())
        gs.start_game()
        self.assertEqual(gs.game_state, STATE_PRELOADING)
        gs.update(gs.min_preload_sec + 0.05, 0.0)
        self.assertEqual(gs.game_state, STATE_PLAYING)
        self.assertIsNotNone(gs.current_quiz)
        self.assertEqual(gs.current_index, 0)

    def test_correct_answer_transitions_to_correct(self):
        gs = QuizGameState(provider=StubProvider(answer=0))
        gs.start_game()
        gs.update(gs.min_preload_sec + 0.05, 0.0)
        gs.player_x = gs.tuning.left_door_x
        gs.wall_z = gs.tuning.hit_z
        gs.resolve_collision()
        self.assertEqual(gs.game_state, STATE_CORRECT)
        self.assertEqual(gs.score, 1)

    def test_wrong_answer_transitions_to_game_over(self):
        gs = QuizGameState(provider=StubProvider(answer=1))
        gs.start_game()
        gs.update(gs.min_preload_sec + 0.05, 0.0)
        gs.player_x = gs.tuning.left_door_x
        gs.wall_z = gs.tuning.hit_z
        gs.resolve_collision()
        self.assertEqual(gs.game_state, STATE_GAME_OVER)
        self.assertIn("GAME OVER", gs.message_text)

    def test_endless_mode_refills_quiz(self):
        gs = QuizGameState(provider=StubProvider(answer=0))
        gs.mode = MODE_ENDLESS
        gs.start_game()
        gs.update(gs.min_preload_sec + 0.05, 0.0)
        gs.player_x = gs.tuning.left_door_x
        gs.resolve_collision()
        self.assertEqual(gs.game_state, STATE_CORRECT)
        gs.update(gs.tuning.correct_hold_sec + 0.01, 0.0)
        self.assertEqual(gs.game_state, STATE_PLAYING)
        self.assertIsNotNone(gs.current_quiz)

    def test_preloading_to_playing_transition(self):
        gs = QuizGameState(provider=EmptyThenReadyProvider())
        gs.start_game()
        self.assertEqual(gs.game_state, STATE_PRELOADING)
        gs.update(gs.min_preload_sec + 0.05, 0.0)
        self.assertEqual(gs.game_state, STATE_PLAYING)
        self.assertIsNotNone(gs.current_quiz)

    def test_menu_step_transitions(self):
        gs = QuizGameState(provider=StubProvider())
        gs.select_mode_and_continue(MODE_ENDLESS)
        self.assertEqual(gs.mode, MODE_ENDLESS)
        self.assertEqual(gs.menu_step, MENU_STEP_CONFIG)
        gs.back_to_mode_select()
        self.assertEqual(gs.menu_step, MENU_STEP_MODE)

    def test_rating_calls_provider_hooks(self):
        provider = StubProvider(answer=1)
        gs = QuizGameState(provider=provider)
        gs.start_game()
        gs.update(gs.min_preload_sec + 0.05, 0.0)
        gs.player_x = gs.tuning.left_door_x
        gs.wall_z = gs.tuning.hit_z
        gs.resolve_collision()  # wrong -> GAME_OVER and rating target set
        gs.rate_last_question(True)
        gs.rate_last_question(False)
        self.assertEqual(provider.good_called, 1)
        self.assertEqual(provider.bad_called, 1)


if __name__ == "__main__":
    unittest.main()
