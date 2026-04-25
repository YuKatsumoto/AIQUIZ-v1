import os
import sys
import math
from pathlib import Path

try:
    from dotenv import load_dotenv
    # `game/app/main_3d.py` -> `game/app` -> `game` -> `AIQUIZ-v1` -> `.../.env`
    # Let dotenv find the .env naturally
    load_dotenv(override=True)
except ImportError:
    pass

import pygame

from game.core.constants import STATE_PLAYING, STATE_CORRECT, STATE_GAME_OVER
from game.core.game_state import QuizGameState
from game.core.quiz_provider import OfflineQuizProvider
from game.core.providers.buffered_provider import BufferedQuizProvider
from game.core.providers.api_status import set_offline_count
from game.core.ratings.ratings_service import RatingsService
from game.render.renderer import Renderer3D
from game.ui.hud import HudRenderer
from game.audio.synth import generate_correct_sound, generate_explosion_sound


def _resolve_bank_path() -> str:
    here = Path(__file__).resolve().parents[2]
    return str(here / "offline_bank.json")


def run():
    try:
        pygame.mixer.init()
    except Exception as e:
        print(f"Warning: Pygame mixer init failed: {e}. Sound will be disabled.")
    pygame.init()
    pygame.font.init()

    width, height = 1280, 720
    
    # Load graphics settings from .env (with defaults)
    msaa_samples = int(os.getenv("MSAA_SAMPLES", "4"))
    vsync_enabled = int(os.getenv("VSYNC", "1"))
    target_fps = int(os.getenv("TARGET_FPS", "120"))
    
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    
    if msaa_samples > 0:
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, msaa_samples)
        
    pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE, vsync=vsync_enabled)
    pygame.display.set_caption("AI脱出クイズ 3D (Engine-Free)")

    try:
        renderer = Renderer3D(width, height)
    except Exception as e:
        print("ModernGL初期化に失敗しました。GPUドライバまたはOpenGL 3.3対応を確認してください。")
        print(e)
        pygame.quit()
        sys.exit(1)

    hud = HudRenderer(width, height)
    offline_provider = OfflineQuizProvider(_resolve_bank_path())
    ratings_service = RatingsService(str(Path(__file__).resolve().parents[2] / "quiz_ratings.json"))
    ratings_service.load()
    provider = BufferedQuizProvider(
        offline_provider=offline_provider,
        ratings_path=str(Path(__file__).resolve().parents[2] / "quiz_ratings.json"),
        reject_log_path=str(Path(__file__).resolve().parents[2] / "quiz_generation_reject_log.jsonl"),
        source_log_path=str(Path(__file__).resolve().parents[2] / "quiz_generation_log.jsonl"),
        num_workers=2,
        ratings_service=ratings_service,
    )
    provider.set_llm_mode(os.getenv("LLM_MODE", "ONLINE"))
    game = QuizGameState(provider=provider, use_english_ui=hud.use_english_ui)

    # Register offline bank count for settings screen
    set_offline_count(offline_provider.total_count())

    # Prepare sounds
    snd_correct = generate_correct_sound()
    snd_wrong = generate_explosion_sound()

    clock = pygame.time.Clock()
    running = True
    fixed_dt = 1.0 / 60.0
    accumulator = 0.0

    def apply_resize(new_w: int, new_h: int):
        nonlocal width, height
        width, height = max(960, int(new_w)), max(540, int(new_h))
        pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE, vsync=vsync_enabled)
        renderer.resize(width, height)
        hud.resize(width, height)

    while running:
        frame_dt = min(0.05, clock.tick(target_fps) / 1000.0)
        accumulator += frame_dt

        mouse_locked = (game.game_state == STATE_PLAYING and game.num_players == 1)
        if pygame.event.get_grab() != mouse_locked:
            pygame.event.set_grab(mouse_locked)
            pygame.mouse.set_visible(not mouse_locked)
            if mouse_locked:
                pygame.mouse.get_rel()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.VIDEORESIZE:
                apply_resize(event.w, event.h)
                continue
            if event.type == pygame.WINDOWSIZECHANGED:
                apply_resize(event.x, event.y)
                continue
            if event.type == pygame.WINDOWMAXIMIZED:
                current_w, current_h = pygame.display.get_window_size()
                apply_resize(current_w, current_h)
                continue
            if event.type == pygame.MOUSEMOTION:
                if mouse_locked:
                    game.camera_yaw -= event.rel[0] * 0.002
                    game.camera_pitch -= event.rel[1] * 0.002
                    game.camera_pitch = max(-math.pi/2.5, min(math.pi/2.5, game.camera_pitch))
                hud.set_mouse_pos(event.pos)
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if hud.handle_click(event.pos, game):
                    continue
            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE and game.game_state == STATE_PLAYING:
                running = False
                break

        keys = pygame.key.get_pressed()
        move_axis = 0.0
        move_axis_p2 = 0.0
        if game.game_state == STATE_PLAYING:
            # Player 1: A/D (always)
            if keys[pygame.K_a]:
                move_axis += 1.0
            if keys[pygame.K_d]:
                move_axis -= 1.0
            if game.num_players >= 2:
                # 2P: Arrow keys control Player 2
                if keys[pygame.K_LEFT]:
                    move_axis_p2 += 1.0
                if keys[pygame.K_RIGHT]:
                    move_axis_p2 -= 1.0
            else:
                # 1P: Arrow keys also control Player 1
                if keys[pygame.K_LEFT]:
                    move_axis += 1.0
                if keys[pygame.K_RIGHT]:
                    move_axis -= 1.0

        while accumulator >= fixed_dt:
            prev_state = game.game_state
            game.update(fixed_dt, move_axis, move_axis_p2)
            
            # Trigger sounds on state transition
            if prev_state != game.game_state:
                if game.game_state == STATE_CORRECT and snd_correct:
                    snd_correct.set_volume(game.sfx_volume)
                    snd_correct.play()
                elif game.game_state == STATE_GAME_OVER and snd_wrong:
                    snd_wrong.set_volume(game.sfx_volume)
                    snd_wrong.play()
                    
            accumulator -= fixed_dt

        hud.set_mouse_pos(pygame.mouse.get_pos())
        ui_surface = hud.render(game)
        renderer.render(game, ui_surface, frame_dt)
        pygame.display.flip()

    if hasattr(provider, "stop"):
        provider.stop()
    pygame.quit()


if __name__ == "__main__":
    # Keep SDL startup noise lower on some environments.
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    run()
