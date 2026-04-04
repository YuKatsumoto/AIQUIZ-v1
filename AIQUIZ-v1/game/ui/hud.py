"""HUD / UI overlay for the 3D Engine-Free quiz game.

Renders all 2-D UI elements onto a transparent Pygame ``Surface`` that the
renderer composites on top of the 3-D scene.
"""

import os
import sys
from dataclasses import dataclass

import pygame

from game.core.constants import (
    MENU_STEP_CONFIG,
    MENU_STEP_MODE,
    MODE_ENDLESS,
    MODE_TEN,
    STATE_CLEAR,
    STATE_CORRECT,
    STATE_GAME_OVER,
    STATE_MENU,
    STATE_PLAYING,
    STATE_PRELOADING,
    SUBJECTS,
)
from game.core.game_state import QuizGameState


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------

def japanese_font_path() -> str:
    if sys.platform == "win32":
        for name in ("meiryo.ttc", "Meiryo.ttf", "msgothic.ttc", "MS Gothic.ttf"):
            p = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", name)
            if os.path.isfile(p):
                return p
    elif sys.platform == "darwin":
        for p in (
            "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ):
            if os.path.isfile(p):
                return p
    return ""


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

@dataclass
class UITheme:
    # Menu
    menu_bg: tuple = (244, 240, 232, 255)
    fg: tuple = (35, 40, 48)
    fg_dark: tuple = (20, 23, 29)
    hint: tuple = (110, 116, 125)
    accent_blue: tuple = (29, 78, 137)
    accent_orange: tuple = (168, 73, 43)
    # In-game
    green: tuple = (50, 220, 80)
    red: tuple = (220, 40, 60)
    white: tuple = (240, 245, 255)
    gold: tuple = (255, 215, 0)
    cyan: tuple = (0, 210, 255)
    # Cards
    hero_card: tuple = (255, 252, 245)
    hero_border: tuple = (214, 204, 183)
    side_card: tuple = (255, 250, 240)
    side_border: tuple = (219, 210, 190)
    # Buttons
    mode_ten_bg: tuple = (237, 244, 252)
    mode_endless_bg: tuple = (252, 240, 232)
    start_btn: tuple = (241, 163, 72)
    chip_bg: tuple = (234, 228, 216)
    chip_border: tuple = (204, 195, 175)
    # Gameplay overlays
    card_bg: tuple = (10, 14, 26, 200)
    card_border: tuple = (60, 80, 130)
    overlay_bg: tuple = (6, 8, 18, 210)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rounded_rect(surf: pygame.Surface, color, rect: pygame.Rect, radius: int = 16, width: int = 0):
    """Draw a rounded rectangle (handles alpha tuple)."""
    if len(color) == 4:
        tmp = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(tmp, color, (0, 0, rect.w, rect.h), width=width, border_radius=radius)
        surf.blit(tmp, rect.topleft)
    else:
        pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)


def _wrap_lines(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    if font.size(text)[0] <= max_w:
        return [text]
    lines: list[str] = []
    cur = ""
    for ch in text:
        t = cur + ch
        if font.size(t)[0] > max_w:
            if cur:
                lines.append(cur)
            cur = ch
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines or [text]


# ---------------------------------------------------------------------------
# HudRenderer
# ---------------------------------------------------------------------------

class HudRenderer:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.theme = UITheme()
        self.ja_font = japanese_font_path()
        self.use_english_ui = not bool(self.ja_font)

        font_name = self.ja_font if self.ja_font else None
        self.font_title = pygame.font.Font(font_name, 44)
        self.font_h2 = pygame.font.Font(font_name, 30)
        self.font_main = pygame.font.Font(font_name, 26)
        self.font_small = pygame.font.Font(font_name, 20)
        self.menu_hitboxes: dict[str, pygame.Rect] = {}
        self._mouse_pos = (0, 0)
        self._image_cache: dict[str, pygame.Surface] = {}
        self._anim_t = 0.0

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.menu_hitboxes = {}

    def set_mouse_pos(self, pos: tuple[int, int]):
        self._mouse_pos = pos

    # -----------------------------------------------------------------------
    # Click handling
    # -----------------------------------------------------------------------

    def handle_menu_click(self, pos: tuple[int, int], game: QuizGameState) -> bool:
        if game.game_state != STATE_MENU:
            return False
        if game.menu_step == MENU_STEP_MODE:
            if self.menu_hitboxes.get("mode_ten", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.select_mode_and_continue(MODE_TEN)
                return True
            if self.menu_hitboxes.get("mode_endless", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.select_mode_and_continue(MODE_ENDLESS)
                return True
            if self.menu_hitboxes.get("settings_continue", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.select_mode_and_continue(game.mode)
                return True
            if self.menu_hitboxes.get("chip_mode_toggle", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.llm_mode = "ONLINE" if game.llm_mode == "OFFLINE" else "OFFLINE"
                game.refresh_status_text()
                return True
            if self.menu_hitboxes.get("chip_diff_toggle", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.cycle_difficulty(1)
                return True
            return False
        # CONFIG step
        if self.menu_hitboxes.get("start_game", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
            game.start_game()
            return True
        if self.menu_hitboxes.get("back_mode", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
            game.back_to_mode_select()
            return True
        for grade in range(1, 7):
            if self.menu_hitboxes.get(f"grade_{grade}", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.grade = grade
                game.refresh_status_text()
                return True
        for subject in SUBJECTS:
            if self.menu_hitboxes.get(f"subject_{subject}", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.subject = subject
                game.refresh_status_text()
                return True
        return False

    def handle_click(self, pos: tuple[int, int], game: QuizGameState) -> bool:
        if game.game_state == STATE_MENU:
            return self.handle_menu_click(pos, game)
        if game.game_state in (STATE_GAME_OVER, STATE_CLEAR):
            if self.menu_hitboxes.get("rate_good", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.rate_last_question(True)
                return True
            if self.menu_hitboxes.get("rate_bad", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.rate_last_question(False)
                return True
            if self.menu_hitboxes.get("back_to_menu", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
                game.reset_to_menu()
                return True
        return False

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _font(self, size: int, bold: bool = False) -> pygame.font.Font:
        f = pygame.font.Font(self.ja_font if self.ja_font else None, size)
        f.set_bold(bold)
        return f

    def _text(self, surf, font, text, x, y, color):
        lh = font.get_height() + 4
        for i, line in enumerate(text.split("\n")):
            img = font.render(line, True, color)
            surf.blit(img, (x, y + i * lh))

    def _text_center(self, surf, font, text, cx, cy, color):
        img = font.render(text, True, color)
        surf.blit(img, img.get_rect(center=(cx, cy)))

    # -----------------------------------------------------------------------
    # Menu drawing (largely preserved from original)
    # -----------------------------------------------------------------------

    def _draw_menu(self, surface: pygame.Surface, game: QuizGameState):
        w, h = self.width, self.height
        surface.fill((244, 240, 232))
        self.menu_hitboxes = {}

        if game.menu_step == MENU_STEP_MODE:
            self._draw_mode_select(surface, game, w, h)
        else:
            self._draw_config_select(surface, game, w, h)

    def _draw_mode_select(self, surface, game, w, h):
        left_x = max(36, int(w * 0.07))
        compact = w < 1080
        content_w = w - left_x * 2 if compact else min(int(w * 0.48), 520)
        panel_x = left_x if compact else max(32, int(w * 0.58))
        panel_w = content_w if compact else min(w - panel_x - 36, 380)

        ft = self._font(58, True)
        fs = self._font(18, True)
        fb = self._font(26, True)
        fcv = self._font(22)
        fm = self._font(18)
        fsm = self._font(16)

        title = ft.render("AI脱出クイズ" if not self.use_english_ui else "AI Escape Quiz", True, (34, 38, 42))
        surface.blit(title, (left_x, int(h * 0.08)))

        badge = pygame.Rect(0, 0, min(300, w // 3), 44)
        badge.topright = (w - 28, 24)
        pygame.draw.rect(surface, (34, 38, 42), badge, border_radius=22)
        bt = fm.render("Player 1", True, (245, 242, 232))
        surface.blit(bt, bt.get_rect(center=badge.center))

        hero_top = int(h * 0.19)
        hero_h = int(h * (0.40 if compact else 0.50))
        hero = pygame.Rect(left_x, hero_top, content_w, hero_h)
        pygame.draw.rect(surface, (255, 252, 245), hero, border_radius=26)
        pygame.draw.rect(surface, (214, 204, 183), hero, width=2, border_radius=26)

        sl = fs.render("PLAY MODE", True, (165, 88, 42))
        surface.blit(sl, (hero.x + 26, hero.y + 22))

        my = hero.y + 62
        mw = hero.w - 52
        mh = 96
        mg = 18
        r_ten = pygame.Rect(hero.x + 26, my, mw, mh)
        r_end = pygame.Rect(hero.x + 26, my + mh + mg, mw, mh)
        self.menu_hitboxes["mode_ten"] = r_ten
        self.menu_hitboxes["mode_endless"] = r_end

        modes = {
            MODE_TEN: ("10問チャレンジ", "10問でスコアを競う短期決戦", (29, 78, 137), (237, 244, 252)),
            MODE_ENDLESS: ("エンドレス", "問題を解き続ける継続プレイ", (168, 73, 43), (252, 240, 232)),
        }
        for mode, rect in ((MODE_TEN, r_ten), (MODE_ENDLESS, r_end)):
            cap, desc, accent, bg = modes[mode]
            active = game.mode == mode
            fill = bg if active else (246, 242, 234)
            if rect.collidepoint(self._mouse_pos):
                fill = tuple(max(0, c - 10) for c in fill)
            pygame.draw.rect(surface, fill, rect, border_radius=22)
            pygame.draw.rect(surface, accent if active else (198, 190, 174), rect,
                             width=3 if active else 2, border_radius=22)
            pygame.draw.rect(surface, accent, (rect.x + 16, rect.y + 16, 10, rect.h - 32), border_radius=5)
            surface.blit(fb.render(cap, True, (28, 32, 36)), (rect.x + 42, rect.y + 18))
            surface.blit(fm.render(desc, True, (96, 101, 106)), (rect.x + 44, rect.y + 56))

        sr = pygame.Rect(hero.x + 26, hero.bottom - 72, mw, 52)
        self.menu_hitboxes["settings_continue"] = sr
        sbg = (241, 163, 72)
        if sr.collidepoint(self._mouse_pos):
            sbg = (228, 152, 66)
        pygame.draw.rect(surface, sbg, sr, border_radius=16)
        st = fb.render("次へ進む" if not self.use_english_ui else "Continue", True, (255, 255, 255))
        surface.blit(st, st.get_rect(center=sr.center))

        # Side panel
        spy = hero.bottom + 22 if compact else hero_top
        sph = int(h * 0.40) if compact else int(h * 0.58)
        sp = pygame.Rect(panel_x, spy, panel_w, sph)
        pygame.draw.rect(surface, (255, 250, 240), sp, border_radius=26)
        pygame.draw.rect(surface, (219, 210, 190), sp, width=2, border_radius=26)
        pt = fs.render("QUICK SETTINGS", True, (75, 79, 84))
        surface.blit(pt, (sp.x + 22, sp.y + 20))

        cx = sp.x + 22
        cw = sp.w - 44
        ch = 74
        cg = 18

        def chip(rect, label, value, bg):
            pygame.draw.rect(surface, bg, rect, border_radius=18)
            pygame.draw.rect(surface, (214, 204, 183), rect, width=2, border_radius=18)
            surface.blit(fm.render(label, True, (92, 97, 103)), (rect.x + 16, rect.y + 10))
            surface.blit(fsm.render("クリックで変更", True, (120, 124, 129)),
                         fsm.render("クリックで変更", True, (120, 124, 129)).get_rect(topright=(rect.right - 16, rect.y + 12)))
            surface.blit(fcv.render(value, True, (32, 37, 42)), (rect.x + 16, rect.y + 38))

        cp = pygame.Rect(cx, sp.y + 58, cw, ch)
        cd = pygame.Rect(cx, cp.bottom + cg, cw, ch)
        cm = pygame.Rect(cx, cd.bottom + cg, cw, ch)
        self.menu_hitboxes["chip_diff_toggle"] = cd
        self.menu_hitboxes["chip_mode_toggle"] = cm
        chip(cp, "プレイヤー数", "1人", (239, 243, 246))
        chip(cd, "難易度", game.difficulty, (242, 239, 231))
        llm = "ONLINE / AI生成" if game.llm_mode == "ONLINE" else "OFFLINE / 内蔵問題"
        chip(cm, "出題方式", llm, (234, 242, 236))

    def _draw_config_select(self, surface, game, w, h):
        left_x = max(36, int(w * 0.07))
        cw = min(w - left_x * 2, 980)
        card_x = (w - cw) // 2
        card_y = int(h * 0.16)
        card_h = int(h * 0.68)

        tf = self._font(46, True)
        sf = self._font(18, True)
        cf = self._font(24, True)
        mf = self._font(18)

        title = tf.render("学年と教科を選択" if not self.use_english_ui else "Select Grade & Subject",
                          True, (34, 38, 42))
        surface.blit(title, (card_x, int(h * 0.07)))

        pygame.draw.rect(surface, (255, 252, 245), (card_x, card_y, cw, card_h), border_radius=26)
        pygame.draw.rect(surface, (214, 204, 183), (card_x, card_y, cw, card_h), width=2, border_radius=26)

        br = pygame.Rect(card_x + cw - 150, int(h * 0.07), 150, 46)
        self.menu_hitboxes["back_mode"] = br
        pygame.draw.rect(surface, (230, 224, 210), br, border_radius=16)
        pygame.draw.rect(surface, (214, 204, 183), br, width=2, border_radius=16)
        bs = self._font(22, True).render("戻る" if not self.use_english_ui else "Back", True, (34, 38, 42))
        surface.blit(bs, bs.get_rect(center=br.center))

        s1 = sf.render("GRADE", True, (165, 88, 42))
        surface.blit(s1, (card_x + 26, card_y + 24))

        gx = 18; gy = 18
        bw = int((cw - 52 - gx * 2) / 3)
        bh = 72
        gax = card_x + 26
        gay = card_y + 58
        for i, g in enumerate([1, 2, 3, 4, 5, 6]):
            x = gax + (i % 3) * (bw + gx)
            y = gay + (i // 3) * (bh + gy)
            r = pygame.Rect(x, y, bw, bh)
            act = game.grade == g
            bg = (34, 38, 42) if act else (248, 245, 238)
            fg = (245, 248, 255) if act else (34, 38, 42)
            pygame.draw.rect(surface, bg, r, border_radius=18)
            pygame.draw.rect(surface, (214, 204, 183), r, width=2, border_radius=18)
            lab = cf.render(f"{g}年生" if not self.use_english_ui else f"Grade {g}", True, fg)
            surface.blit(lab, lab.get_rect(center=r.center))
            self.menu_hitboxes[f"grade_{g}"] = r

        s2 = sf.render("SUBJECT", True, (165, 88, 42))
        surface.blit(s2, (card_x + 26, card_y + int(card_h * 0.48)))

        sg = 18
        sw = int((cw - 52 - sg * 2) / 3)
        sh = 76
        say = card_y + int(card_h * 0.56)
        for i, s in enumerate(SUBJECTS):
            x = gax + i * (sw + sg)
            r = pygame.Rect(x, say, sw, sh)
            act = game.subject == s
            bg = (34, 38, 42) if act else (248, 245, 238)
            fg = (245, 248, 255) if act else (34, 38, 42)
            pygame.draw.rect(surface, bg, r, border_radius=18)
            pygame.draw.rect(surface, (214, 204, 183), r, width=2, border_radius=18)
            lab = cf.render(s, True, fg)
            surface.blit(lab, lab.get_rect(center=r.center))
            self.menu_hitboxes[f"subject_{s}"] = r

        sr = pygame.Rect(card_x + 26, card_y + card_h - 58, cw - 52, 54)
        self.menu_hitboxes["start_game"] = sr
        note = mf.render("選択した設定でゲームを開始", True, (120, 124, 129))
        surface.blit(note, (sr.x, sr.y - 28))
        pygame.draw.rect(surface, (241, 163, 72), sr, border_radius=18)
        ss = self._font(34, True).render("ゲーム開始" if not self.use_english_ui else "Start Game",
                                         True, (245, 248, 255))
        surface.blit(ss, ss.get_rect(center=sr.center))

    # -----------------------------------------------------------------------
    # Gameplay HUD (redesigned)
    # -----------------------------------------------------------------------

    def _draw_play(self, surface: pygame.Surface, game: QuizGameState):
        w, h = self.width, self.height
        t = self.theme
        self._anim_t += 1.0 / 60.0  # approximate

        # --- Preloading ---
        if game.game_state == STATE_PRELOADING:
            self._draw_preloading(surface, game, w, h)
            return

        # --- Question card (top center) ---
        q = game.question_text()
        if q:
            card_w = min(int(w * 0.75), 840)
            card_x = (w - card_w) // 2
            card_y = 18

            lines = _wrap_lines(q, self.font_main, card_w - 48)
            line_h = self.font_main.get_height() + 4
            card_h = max(70, 28 + len(lines) * line_h + 16)

            card = pygame.Rect(card_x, card_y, card_w, card_h)
            _rounded_rect(surface, t.card_bg, card, radius=18)
            _rounded_rect(surface, t.card_border, card, radius=18, width=2)

            # glowing accent line at top of card
            accent_r = pygame.Rect(card_x + 20, card_y, card_w - 40, 3)
            _rounded_rect(surface, (0, 200, 255, 180), accent_r, radius=2)

            y = card_y + 18
            for line in lines:
                ts = self.font_main.render(line, True, t.white)
                surface.blit(ts, ((w - ts.get_width()) // 2, y))
                y += line_h

        # --- Choice hints (below question card) ---
        if game.current_quiz and game.game_state == STATE_PLAYING:
            ltext, rtext = game.choices_text()
            hint_y = card_y + card_h + 10 if q else 24
            # Left hint
            lf = self.font_small.render(ltext, True, (255, 150, 80))
            surface.blit(lf, (32, hint_y))
            # Right hint
            rf = self.font_small.render(rtext, True, (100, 170, 255))
            surface.blit(rf, rf.get_rect(topright=(w - 32, hint_y)))

        # --- Score / Progress indicator (top right) ---
        if game.game_state in (STATE_PLAYING, STATE_CORRECT):
            if game.mode == MODE_TEN:
                prog = f"{game.current_index + 1}/10"
            else:
                prog = f"Score: {game.score}"
            score_font = self._font(22, True)
            ss = score_font.render(prog, True, t.cyan)
            sr = ss.get_rect(topright=(w - 24, 12))
            bg_r = sr.inflate(20, 12)
            _rounded_rect(surface, (10, 14, 26, 180), bg_r, radius=10)
            surface.blit(ss, sr)

        # --- Progress bar (10Q mode, bottom center) ---
        if game.mode == MODE_TEN and game.game_state in (STATE_PLAYING, STATE_CORRECT):
            bar_total_w = min(400, int(w * 0.5))
            bar_h = 12
            bar_x = (w - bar_total_w) // 2
            bar_y = h - 42
            # Background track
            pygame.draw.rect(surface, (40, 50, 70),
                             (bar_x, bar_y, bar_total_w, bar_h),
                             border_radius=6)
            # Fill
            progress = game.current_index / 10.0
            fill_w = max(0, int(bar_total_w * progress))
            if fill_w > 0:
                pygame.draw.rect(surface, t.cyan,
                                 (bar_x, bar_y, fill_w, bar_h),
                                 border_radius=6)
            # Label
            prog_text = f"{game.current_index}/10"
            pt = self.font_small.render(prog_text, True, (180, 190, 210))
            surface.blit(pt, pt.get_rect(center=(w // 2, bar_y + bar_h + 14)))

        # --- Image display ---
        img_path = ""
        if game.current_quiz and getattr(game.current_quiz, "img", ""):
            img_path = str(game.current_quiz.img).strip()
        if img_path:
            if img_path not in self._image_cache:
                loaded = None
                try:
                    if os.path.isfile(img_path):
                        loaded = pygame.image.load(img_path).convert_alpha()
                except Exception:
                    loaded = None
                self._image_cache[img_path] = loaded
            img = self._image_cache.get(img_path)
            if img:
                max_iw = min(380, w - 64)
                max_ih = 220
                sc = min(max_iw / max(1, img.get_width()), max_ih / max(1, img.get_height()), 1.0)
                di = pygame.transform.smoothscale(
                    img, (max(1, int(img.get_width() * sc)), max(1, int(img.get_height() * sc))))
                ix = (w - di.get_width()) // 2
                iy = 140
                frame = di.get_rect(topleft=(ix, iy)).inflate(12, 12)
                _rounded_rect(surface, (10, 14, 26, 180), frame, radius=12)
                surface.blit(di, (ix, iy))

        # Controls hint removed per user spec

        # --- Status bar ---
        if game.status_text and game.game_state == STATE_PLAYING:
            st = self.font_small.render(game.status_text, True, (90, 100, 130))
            surface.blit(st, st.get_rect(bottomright=(w - 24, h - 8)))

        # --- Correct flash ---
        if game.game_state == STATE_CORRECT:
            txt = "正解！" if not self.use_english_ui else "Correct!"
            big = self._font(56, True)
            ts = big.render(txt, True, t.green)
            tr = ts.get_rect(center=(w // 2, h // 2))
            # glow background
            gbg = tr.inflate(60, 30)
            _rounded_rect(surface, (10, 40, 20, 160), gbg, radius=20)
            surface.blit(ts, tr)

        # --- Game Over / Clear overlay ---
        if game.game_state in (STATE_GAME_OVER, STATE_CLEAR):
            self._draw_result_overlay(surface, game, w, h)

    # -----------------------------------------------------------------------
    # Result overlay (Game Over / Clear)
    # -----------------------------------------------------------------------

    def _draw_result_overlay(self, surface, game, w, h):
        t = self.theme
        # full-screen dim
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill(t.overlay_bg)
        surface.blit(overlay, (0, 0))

        is_clear = game.game_state == STATE_CLEAR
        col = t.gold if is_clear else t.red

        # Title
        big = self._font(52, True)
        title_text = "CLEAR!" if is_clear else "GAME OVER"
        ts = big.render(title_text, True, col)
        surface.blit(ts, ts.get_rect(center=(w // 2, int(h * 0.18))))

        # Message panel
        panel_w = min(int(w * 0.8), 700)
        panel_x = (w - panel_w) // 2
        panel_y = int(h * 0.28)

        msg_lines = game.message_text.split("\n")
        line_h = self.font_main.get_height() + 6
        panel_h = max(100, 30 + len(msg_lines) * line_h + 20)

        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        _rounded_rect(surface, (16, 20, 36, 220), panel, radius=18)
        _rounded_rect(surface, (80, 90, 130), panel, radius=18, width=2)

        y = panel_y + 20
        for line in msg_lines:
            if not line.strip():
                y += 8
                continue
            ts = self.font_main.render(line, True, t.white)
            surface.blit(ts, (panel_x + 28, y))
            y += line_h

        # Rating buttons
        btn_y = panel.bottom + 30
        if game.rating_target_quiz and not game.rating_feedback:
            q_text = game.rating_target_quiz.q or ""
            if len(q_text) > 35:
                q_text = q_text[:35] + "..."
            ql = self.font_small.render(
                f"この問題: {q_text}" if not self.use_english_ui else f"Rate this Q: {q_text}",
                True, (180, 190, 210))
            surface.blit(ql, ql.get_rect(center=(w // 2, btn_y)))
            btn_y += 36

            gw, gh = 140, 48
            gr = pygame.Rect(w // 2 - gw - 12, btn_y, gw, gh)
            br = pygame.Rect(w // 2 + 12, btn_y, gw, gh)
            self.menu_hitboxes["rate_good"] = gr
            self.menu_hitboxes["rate_bad"] = br

            g_hover = gr.collidepoint(self._mouse_pos)
            b_hover = br.collidepoint(self._mouse_pos)
            g_bg = (60, 180, 80) if g_hover else (50, 160, 70)
            b_bg = (200, 60, 60) if b_hover else (180, 50, 50)
            pygame.draw.rect(surface, g_bg, gr, border_radius=14)
            pygame.draw.rect(surface, b_bg, br, border_radius=14)
            gt = self.font_main.render("◯ 良い" if not self.use_english_ui else "Good", True, t.white)
            bt = self.font_main.render("× 悪い" if not self.use_english_ui else "Bad", True, t.white)
            surface.blit(gt, gt.get_rect(center=gr.center))
            surface.blit(bt, bt.get_rect(center=br.center))
            btn_y += gh + 24
        elif game.rating_feedback:
            fb = self.font_main.render(game.rating_feedback, True, t.green)
            surface.blit(fb, fb.get_rect(center=(w // 2, btn_y + 10)))
            btn_y += 52

        # Back to menu button
        menu_btn = pygame.Rect(w // 2 - 150, btn_y, 300, 56)
        self.menu_hitboxes["back_to_menu"] = menu_btn
        m_hover = menu_btn.collidepoint(self._mouse_pos)
        mbg = (60, 70, 100) if m_hover else (45, 55, 85)
        pygame.draw.rect(surface, mbg, menu_btn, border_radius=16)
        pygame.draw.rect(surface, (100, 120, 170), menu_btn, width=2, border_radius=16)
        mt = self.font_main.render("メニューに戻る" if not self.use_english_ui else "Back to Menu",
                                   True, t.white)
        surface.blit(mt, mt.get_rect(center=menu_btn.center))

    # -----------------------------------------------------------------------
    # Preloading screen
    # -----------------------------------------------------------------------

    def _draw_preloading(self, surface, game, w, h):
        t = self.theme
        card_w = min(560, int(w * 0.7))
        card_h = 200
        card = pygame.Rect((w - card_w) // 2, (h - card_h) // 2, card_w, card_h)
        _rounded_rect(surface, (12, 16, 30, 230), card, radius=22)
        _rounded_rect(surface, (60, 80, 130), card, radius=22, width=2)

        # Animated dots
        dots = "." * (int(self._anim_t * 2) % 4)
        loading = "問題を準備中" + dots if not self.use_english_ui else "Loading quizzes" + dots
        ls = self.font_h2.render(loading, True, t.white)
        surface.blit(ls, ls.get_rect(center=(w // 2, card.y + 50)))

        sub = "しばらくお待ちください" if not self.use_english_ui else "Please wait"
        ss = self.font_small.render(sub, True, (160, 175, 210))
        surface.blit(ss, ss.get_rect(center=(w // 2, card.y + 95)))

        # Progress bar
        bar_w = card_w - 80
        bar_h = 14
        bar_x = card.x + 40
        bar_y = card.y + 130
        pygame.draw.rect(surface, (30, 38, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=7)

        # Animated shimmer
        progress = min(0.95, self._anim_t / 5.0)  # rough estimate
        fill_w = max(4, int(bar_w * progress))
        pygame.draw.rect(surface, (0, 180, 240), (bar_x, bar_y, fill_w, bar_h), border_radius=7)

        # Status line
        st = self.font_small.render(game.status_text, True, (120, 135, 170))
        surface.blit(st, st.get_rect(center=(w // 2, card.y + 165)))

    # -----------------------------------------------------------------------
    # Main render
    # -----------------------------------------------------------------------

    def render(self, game: QuizGameState) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        if game.game_state == STATE_MENU:
            self._draw_menu(surface, game)
        else:
            self._draw_play(surface, game)
        return surface
