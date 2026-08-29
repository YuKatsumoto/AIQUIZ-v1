import os
import sys

# ヘッドレス（ウィンドウを開かない）でPygameを動作させる設定
os.environ["SDL_VIDEODRIVER"] = "dummy"

# 2D_pygame.py のインポートパスを通す
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pygame
import unittest

# sys.exitをモック化（2D_pygameインポート時の終了を回避）
original_exit = sys.exit
sys.exit = lambda *args: None

# importlibを使用して数字で始まるファイル名をインポート
import importlib
game = importlib.import_module("2D_pygame")

# モックを戻す
sys.exit = original_exit

class Test2DGame4Choice(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.font.init()
        # プレイヤー設定のモック
        game.PLAYER_CONFIGS[1] = {
            "name": "Player 1",
            "grade": 3, 
            "subject": "算数",
            "difficulties": {"算数": "難しい", "理科": "普通", "国語": "普通"},
            "subject_grades": {"算数": 3, "理科": 3, "国語": 3}
        }
        self.viewport = pygame.Rect(0, 0, 960, 720)
        self.player = game.Player(1, self.viewport, pygame.K_LEFT, pygame.K_RIGHT)

    def test_4choice_geometry_setup(self):
        # 4択クイズを設定
        self.player.current_quiz = {
            "q": "1+1は？",
            "c": ["1", "2", "3", "4"],
            "a": 1,
            "e": "1+1は2です"
        }
        
        # ジオメトリリセット
        self.player.reset_geometry()
        
        # 検証1: ドアの数が4つであること
        self.assertEqual(len(self.player.doors), 4)
        
        # 検証2: door1 と door2 が互換性のために保持されていること
        self.assertEqual(self.player.door1, self.player.doors[0])
        self.assertEqual(self.player.door2, self.player.doors[1])
        
        # 検証3: ドアの幅が4択用に縮小されていること (0.14)
        expected_width = int(self.viewport.width * 0.14)
        self.assertEqual(self.player.doors[0].width, expected_width)
        
        # 検証4: ドアが等間隔に並んでいること
        # 各ドアの中心座標が正しいことを確認
        for i in range(4):
            expected_center_x = self.viewport.left + (self.viewport.width / 4) * (i + 0.5)
            self.assertAlmostEqual(self.player.doors[i].centerx, expected_center_x, delta=1.0)

    def test_4choice_prepare_surfaces(self):
        self.player.current_quiz = {
            "q": "1+1は？",
            "c": ["1", "2", "3", "4"],
            "a": 1,
            "e": "1+1は2です"
        }
        # ジオメトリリセット
        self.player.reset_geometry()
        
        # 例外が発生せずにサーフェスが準備できること
        try:
            self.player.prepare_surfaces()
        except Exception as e:
            self.fail(f"prepare_surfaces raised exception: {e}")
            
        # サーフェス数の検証
        self.assertEqual(len(self.player.choice_surfs), 4)
        self.assertEqual(len(self.player.choice_rects), 4)

    def test_4choice_correct_collision(self):
        # 正解はインデックス1 ("2")
        self.player.current_quiz = {
            "q": "1+1は？",
            "c": ["1", "2", "3", "4"],
            "a": 1,
            "e": "1+1は2です"
        }
        self.player.reset_geometry()
        self.player.prepare_surfaces()
        self.player.state = "PLAYING"
        
        # プレイヤーを正解のドア（インデックス1、つまりdoors[1]）のX座標に配置
        target_door = self.player.doors[1]
        self.player.player.centerx = target_door.centerx
        
        # 壁をプレイヤーの位置まで下ろして衝突させる
        self.player.wall.y = self.player.player.y
        for door in self.player.doors:
            door.y = self.player.wall.y
            
        # キー入力なしのダミーステートとして本物のScancodeWrapperを使用
        keys = pygame.key.get_pressed()
        
        # アップデート実行
        self.player.update(keys)
        
        # 検証: 衝突して正解（"CORRECT"）状態になること
        self.assertEqual(self.player.state, "CORRECT")
        self.assertEqual(len(self.player.history), 1)
        self.assertTrue(self.player.history[0]["was_correct"])
        self.assertEqual(self.player.history[0]["player_choice"], 1)

    def test_4choice_wrong_collision(self):
        # 正解はインデックス1 ("2")
        self.player.current_quiz = {
            "q": "1+1は？",
            "c": ["1", "2", "3", "4"],
            "a": 1,
            "e": "1+1は2です"
        }
        self.player.reset_geometry()
        self.player.prepare_surfaces()
        self.player.state = "PLAYING"
        
        # プレイヤーを不正解のドア（インデックス2、つまりdoors[2]）のX座標に配置
        target_door = self.player.doors[2]
        self.player.player.centerx = target_door.centerx
        
        # 壁をプレイヤーの位置まで下ろして衝突させる
        self.player.wall.y = self.player.player.y
        for door in self.player.doors:
            door.y = self.player.wall.y
            
        keys = pygame.key.get_pressed()
        
        # アップデート実行
        self.player.update(keys)
        
        # 検証: 衝突して不正解（"GAME_OVER"）状態になること
        self.assertEqual(self.player.state, "GAME_OVER")
        self.assertEqual(len(self.player.history), 1)
        self.assertFalse(self.player.history[0]["was_correct"])
        self.assertEqual(self.player.history[0]["player_choice"], 2)
        # 解説情報が保存されていること
        self.assertIsNotNone(self.player.last_incorrect)
        self.assertEqual(self.player.last_incorrect["choice"], 2)

if __name__ == "__main__":
    unittest.main()
