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
    STATE_PRELOADING,
    SUBJECTS,
)
from game.core.game_state import QuizGameState


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


@dataclass
class UITheme:
    menu_bg: tuple[int, int, int, int] = (244, 240, 232, 255)
    fg: tuple[int, int, int] = (35, 40, 48)
    fg_dark: tuple[int, int, int] = (20, 23, 29)
    hint: tuple[int, int, int] = (110, 116, 125)
    accent_blue: tuple[int, int, int] = (29, 78, 137)
    accent_orange: tuple[int, int, int] = (168, 73, 43)
    green: tuple[int, int, int] = (50, 205, 50)
    red: tuple[int, int, int] = (220, 20, 60)
    white: tuple[int, int, int] = (245, 248, 255)
    gold: tuple[int, int, int] = (255, 215, 0)
    hero_card: tuple[int, int, int] = (255, 252, 245)
    hero_border: tuple[int, int, int] = (214, 204, 183)
    side_card: tuple[int, int, int] = (255, 250, 240)
    side_border: tuple[int, int, int] = (219, 210, 190)
    mode_ten_bg: tuple[int, int, int] = (237, 244, 252)
    mode_endless_bg: tuple[int, int, int] = (252, 240, 232)
    start_btn: tuple[int, int, int] = (241, 163, 72)
    chip_bg: tuple[int, int, int] = (234, 228, 216)
    chip_border: tuple[int, int, int] = (204, 195, 175)


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

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.menu_hitboxes = {}

    def set_mouse_pos(self, pos: tuple[int, int]):
        self._mouse_pos = pos

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

    def _font(self, size: int, bold: bool = False) -> pygame.font.Font:
        font = pygame.font.Font(self.ja_font if self.ja_font else None, size)
        font.set_bold(bold)
        return font

    def _draw_menu_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        title: str,
        desc: str,
        accent: tuple[int, int, int],
        bg: tuple[int, int, int],
        active: bool,
    ):
        mouse_over = rect.collidepoint(self._mouse_pos)
        fill = bg if active else (246, 242, 234)
        if mouse_over:
            fill = tuple(max(0, min(255, c - 10)) for c in fill)
        pygame.draw.rect(surface, fill, rect, border_radius=18)
        pygame.draw.rect(surface, accent if active else (198, 190, 174), rect, width=3 if active else 2, border_radius=18)

        pygame.draw.rect(surface, accent, (rect.x + 16, rect.y + 16, 10, rect.h - 32), border_radius=5)
        cap_font = self._font(26, bold=True)
        desc_font = self._font(18)
        cap = cap_font.render(title, True, (28, 32, 36))
        desc_surf = desc_font.render(desc, True, (96, 101, 106))
        surface.blit(cap, (rect.x + 42, rect.y + 18))
        surface.blit(desc_surf, (rect.x + 44, rect.y + 56))

    def _draw_text(self, surface: pygame.Surface, font: pygame.font.Font, text: str, x: int, y: int, color):
        line_h = font.get_height() + 4
        for i, line in enumerate(text.split("\n")):
            img = font.render(line, True, color)
            surface.blit(img, (x, y + i * line_h))

    def _draw_menu(self, surface: pygame.Surface, game: QuizGameState):
        # Directly ported layout style from 2D_pygame.py (draw_title/draw_select)
        w, h = self.width, self.height
        surface.fill((244, 240, 232))
        self.menu_hitboxes = {}

        if game.menu_step == MENU_STEP_MODE:
            left_x = max(36, int(w * 0.07))
            compact_layout = w < 1080
            if compact_layout:
                content_w = w - left_x * 2
                panel_x = left_x
                panel_w = content_w
            else:
                content_w = min(int(w * 0.48), 520)
                panel_x = max(32, int(w * 0.58))
                panel_w = min(w - panel_x - 36, 380)

            font_title = self._font(58, bold=True)
            font_section = self._font(18, bold=True)
            font_button = self._font(26, bold=True)
            font_chip_value = self._font(22)
            font_meta = self._font(18)
            font_small = self._font(16)

            title_main = font_title.render("AI脱出クイズ" if not self.use_english_ui else "AI Escape Quiz", True, (34, 38, 42))
            surface.blit(title_main, (left_x, int(h * 0.08)))

            badge = pygame.Rect(0, 0, min(300, w // 3), 44)
            badge.topright = (w - 28, 24)
            pygame.draw.rect(surface, (34, 38, 42), badge, border_radius=22)
            badge_text = font_meta.render("Player 1", True, (245, 242, 232))
            surface.blit(badge_text, badge_text.get_rect(center=badge.center))

            hero_top = int(h * 0.19)
            hero_card_h = int(h * (0.40 if compact_layout else 0.50))
            hero_card = pygame.Rect(left_x, hero_top, content_w, hero_card_h)
            pygame.draw.rect(surface, (255, 252, 245), hero_card, border_radius=26)
            pygame.draw.rect(surface, (214, 204, 183), hero_card, width=2, border_radius=26)

            section_label = font_section.render("PLAY MODE", True, (165, 88, 42))
            surface.blit(section_label, (hero_card.x + 26, hero_card.y + 22))

            mode_gap = 18
            mode_y = hero_card.y + 62
            mode_w = hero_card.w - 52
            mode_h = 96
            mode_ten_rect = pygame.Rect(hero_card.x + 26, mode_y, mode_w, mode_h)
            mode_endless_rect = pygame.Rect(hero_card.x + 26, mode_y + mode_h + mode_gap, mode_w, mode_h)
            self.menu_hitboxes["mode_ten"] = mode_ten_rect
            self.menu_hitboxes["mode_endless"] = mode_endless_rect

            mode_desc = {
                MODE_TEN: ("10問チャレンジ", "10問でスコアを競う短期決戦"),
                MODE_ENDLESS: ("エンドレス", "問題を解き続ける継続プレイ"),
            }
            mode_colors = {
                MODE_TEN: ((29, 78, 137), (237, 244, 252)),
                MODE_ENDLESS: ((168, 73, 43), (252, 240, 232)),
            }
            for mode, rect in ((MODE_TEN, mode_ten_rect), (MODE_ENDLESS, mode_endless_rect)):
                accent, bg = mode_colors[mode]
                active = game.mode == mode
                fill = bg if active else (246, 242, 234)
                pygame.draw.rect(surface, fill, rect, border_radius=22)
                pygame.draw.rect(surface, accent if active else (198, 190, 174), rect, width=3 if active else 2, border_radius=22)
                pygame.draw.rect(surface, accent, (rect.x + 16, rect.y + 16, 10, rect.h - 32), border_radius=5)
                cap, desc = mode_desc[mode]
                cap_surf = font_button.render(cap, True, (28, 32, 36))
                desc_surf = font_meta.render(desc, True, (96, 101, 106))
                surface.blit(cap_surf, (rect.x + 42, rect.y + 18))
                surface.blit(desc_surf, (rect.x + 44, rect.y + 56))

            settings_rect = pygame.Rect(hero_card.x + 26, hero_card.bottom - 72, mode_w, 52)
            self.menu_hitboxes["settings_continue"] = settings_rect
            settings_bg = (241, 163, 72)
            if settings_rect.collidepoint(self._mouse_pos):
                settings_bg = (228, 152, 66)
            pygame.draw.rect(surface, settings_bg, settings_rect, border_radius=16)
            settings_text = font_button.render("難易度・詳細設定" if not self.use_english_ui else "Continue", True, (255, 255, 255))
            surface.blit(settings_text, settings_text.get_rect(center=settings_rect.center))

            side_panel_y = hero_card.bottom + 22 if compact_layout else hero_top
            side_panel_h = int(h * 0.40) if compact_layout else int(h * 0.58)
            side_panel = pygame.Rect(panel_x, side_panel_y, panel_w, side_panel_h)
            pygame.draw.rect(surface, (255, 250, 240), side_panel, border_radius=26)
            pygame.draw.rect(surface, (219, 210, 190), side_panel, width=2, border_radius=26)
            panel_title = font_section.render("QUICK SETTINGS", True, (75, 79, 84))
            surface.blit(panel_title, (side_panel.x + 22, side_panel.y + 20))

            chip_x = side_panel.x + 22
            chip_w = side_panel.w - 44
            chip_h = 74
            chip_gap = 18

            def draw_chip(rect: pygame.Rect, label: str, value: str, bg: tuple[int, int, int]):
                pygame.draw.rect(surface, bg, rect, border_radius=18)
                pygame.draw.rect(surface, (214, 204, 183), rect, width=2, border_radius=18)
                label_surf = font_meta.render(label, True, (92, 97, 103))
                surface.blit(label_surf, (rect.x + 16, rect.y + 10))
                hint_surf = font_small.render("クリックで変更", True, (120, 124, 129))
                surface.blit(hint_surf, hint_surf.get_rect(topright=(rect.right - 16, rect.y + 12)))
                value_surf = font_chip_value.render(value, True, (32, 37, 42))
                surface.blit(value_surf, (rect.x + 16, rect.y + 38))

            chip_player = pygame.Rect(chip_x, side_panel.y + 58, chip_w, chip_h)
            chip_diff = pygame.Rect(chip_x, chip_player.bottom + chip_gap, chip_w, chip_h)
            chip_mode = pygame.Rect(chip_x, chip_diff.bottom + chip_gap, chip_w, chip_h)
            self.menu_hitboxes["chip_diff_toggle"] = chip_diff
            self.menu_hitboxes["chip_mode_toggle"] = chip_mode
            draw_chip(chip_player, "プレイヤー数", "1人", (239, 243, 246))
            draw_chip(chip_diff, "難易度", game.difficulty, (242, 239, 231))
            llm_value = "ONLINE / AI生成" if game.llm_mode == "ONLINE" else "OFFLINE / 内蔵問題"
            draw_chip(chip_mode, "出題方式", llm_value, (234, 242, 236))
            return

        # CONFIG screen port (2D draw_select/layout_select style)
        left_x = max(36, int(w * 0.07))
        card_w = min(w - left_x * 2, 980)
        card_x = (w - card_w) // 2
        card_y = int(h * 0.16)
        card_h = int(h * 0.68)

        title_font = self._font(46, bold=True)
        section_font = self._font(18, bold=True)
        chip_font = self._font(24, bold=True)
        meta_font = self._font(18)

        title = title_font.render("学年と教科を選択" if not self.use_english_ui else "Select Grade and Subject", True, (34, 38, 42))
        surface.blit(title, (card_x, int(h * 0.07)))

        pygame.draw.rect(surface, (255, 252, 245), (card_x, card_y, card_w, card_h), border_radius=26)
        pygame.draw.rect(surface, (214, 204, 183), (card_x, card_y, card_w, card_h), width=2, border_radius=26)

        back_rect = pygame.Rect(card_x + card_w - 150, int(h * 0.07), 150, 46)
        self.menu_hitboxes["back_mode"] = back_rect
        pygame.draw.rect(surface, (230, 224, 210), back_rect, border_radius=16)
        pygame.draw.rect(surface, (214, 204, 183), back_rect, width=2, border_radius=16)
        back_surf = self._font(22, bold=True).render("戻る" if not self.use_english_ui else "Back", True, (34, 38, 42))
        surface.blit(back_surf, back_surf.get_rect(center=back_rect.center))

        section1 = section_font.render("GRADE", True, (165, 88, 42))
        surface.blit(section1, (card_x + 26, card_y + 24))

        gap_x = 18
        gap_y = 18
        btn_w = int((card_w - 52 - gap_x * 2) / 3)
        btn_h = 72
        grade_area_x = card_x + 26
        grade_area_y = card_y + 58
        for i, g in enumerate([1, 2, 3, 4, 5, 6]):
            x = grade_area_x + (i % 3) * (btn_w + gap_x)
            y = grade_area_y + (i // 3) * (btn_h + gap_y)
            r = pygame.Rect(x, y, btn_w, btn_h)
            active = game.grade == g
            bg = (34, 38, 42) if active else (248, 245, 238)
            fg = (245, 248, 255) if active else (34, 38, 42)
            pygame.draw.rect(surface, bg, r, border_radius=18)
            pygame.draw.rect(surface, (214, 204, 183), r, width=2, border_radius=18)
            lab = chip_font.render(f"{g}年生" if not self.use_english_ui else f"Grade {g}", True, fg)
            surface.blit(lab, lab.get_rect(center=r.center))
            self.menu_hitboxes[f"grade_{g}"] = r

        section2 = section_font.render("SUBJECT", True, (165, 88, 42))
        surface.blit(section2, (card_x + 26, card_y + int(card_h * 0.48)))

        subj_gap = 18
        subj_w = int((card_w - 52 - subj_gap * 2) / 3)
        subj_h = 76
        subject_area_y = card_y + int(card_h * 0.56)
        for i, s in enumerate(SUBJECTS):
            x = grade_area_x + i * (subj_w + subj_gap)
            r = pygame.Rect(x, subject_area_y, subj_w, subj_h)
            active = game.subject == s
            bg = (34, 38, 42) if active else (248, 245, 238)
            fg = (245, 248, 255) if active else (34, 38, 42)
            pygame.draw.rect(surface, bg, r, border_radius=18)
            pygame.draw.rect(surface, (214, 204, 183), r, width=2, border_radius=18)
            lab = chip_font.render(s, True, fg)
            surface.blit(lab, lab.get_rect(center=r.center))
            self.menu_hitboxes[f"subject_{s}"] = r

        start_rect = pygame.Rect(card_x + 26, card_y + card_h - 58, card_w - 52, 54)
        self.menu_hitboxes["start_game"] = start_rect
        start_note = meta_font.render("選択した設定でゲームを開始", True, (120, 124, 129))
        surface.blit(start_note, (start_rect.x, start_rect.y - 28))
        pygame.draw.rect(surface, (241, 163, 72), start_rect, border_radius=18)
        start_surf = self._font(34, bold=True).render("ゲーム開始" if not self.use_english_ui else "Start Game", True, (245, 248, 255))
        surface.blit(start_surf, start_surf.get_rect(center=start_rect.center))

    def _draw_play(self, surface: pygame.Surface, game: QuizGameState):
        t = self.theme
        if game.game_state == STATE_PRELOADING:
            card = pygame.Rect(self.width // 2 - 270, self.height // 2 - 110, 540, 220)
            pygame.draw.rect(surface, (16, 20, 34, 230), card, border_radius=20)
            pygame.draw.rect(surface, (70, 88, 128), card, width=2, border_radius=20)
            loading = "Loading quizzes..." if self.use_english_ui else "問題を事前取得中..."
            sub = "Please wait" if self.use_english_ui else "しばらくお待ちください"
            self._draw_text(surface, self.font_h2, loading, card.x + 34, card.y + 34, t.white)
            self._draw_text(surface, self.font_main, sub, card.x + 34, card.y + 88, (205, 216, 235))
            self._draw_text(surface, self.font_small, game.status_text, card.x + 34, card.y + 140, (165, 182, 212))
            return

        q = game.question_text()
        l, r = game.choices_text()
        self._draw_text(surface, self.font_main, q, 32, 24, t.white)
        self._draw_text(surface, self.font_main, l, 32, 72, (115, 190, 255))
        self._draw_text(surface, self.font_main, r, 32, 108, (255, 172, 98))
        self._draw_text(surface, self.font_small, game.status_text, 32, 146, (225, 230, 242))

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
                max_w = min(420, self.width - 64)
                max_h = 240
                scale = min(max_w / max(1, img.get_width()), max_h / max(1, img.get_height()), 1.0)
                draw_img = pygame.transform.smoothscale(
                    img,
                    (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale))),
                )
                surface.blit(draw_img, (32, 182))

        help_text = "Move: A/D or arrows | Quit: Esc" if self.use_english_ui else "移動: A/D or ←/→ | 終了: Esc"
        self._draw_text(surface, self.font_small, help_text, 32, self.height - 42, (210, 214, 223))

        if game.game_state in (STATE_CORRECT, STATE_GAME_OVER, STATE_CLEAR):
            msg_color = t.green if game.game_state == STATE_CORRECT else (t.gold if game.game_state == STATE_CLEAR else t.red)
            self._draw_text(surface, self.font_h2, game.message_text, 32, self.height - 180, msg_color)
        if game.game_state in (STATE_GAME_OVER, STATE_CLEAR):
            good_rect = pygame.Rect(self.width - 560, self.height - 70, 120, 46)
            bad_rect = pygame.Rect(self.width - 430, self.height - 70, 120, 46)
            back_rect = pygame.Rect(self.width - 280, self.height - 70, 240, 46)
            self.menu_hitboxes["rate_good"] = good_rect
            self.menu_hitboxes["rate_bad"] = bad_rect
            self.menu_hitboxes["back_to_menu"] = back_rect
            good_hover = good_rect.collidepoint(self._mouse_pos)
            bad_hover = bad_rect.collidepoint(self._mouse_pos)
            hover = back_rect.collidepoint(self._mouse_pos)
            good_bg = (238, 207, 120) if not good_hover else (224, 191, 100)
            bad_bg = (206, 215, 232) if not bad_hover else (189, 199, 219)
            pygame.draw.rect(surface, good_bg, good_rect, border_radius=14)
            pygame.draw.rect(surface, bad_bg, bad_rect, border_radius=14)
            pygame.draw.rect(surface, (214, 204, 183), good_rect, width=2, border_radius=14)
            pygame.draw.rect(surface, (214, 204, 183), bad_rect, width=2, border_radius=14)
            bg = (230, 224, 210) if not hover else (216, 208, 193)
            pygame.draw.rect(surface, bg, back_rect, border_radius=14)
            pygame.draw.rect(surface, (214, 204, 183), back_rect, width=2, border_radius=14)
            good_text = "Good" if self.use_english_ui else "良い"
            bad_text = "Bad" if self.use_english_ui else "悪い"
            gsurf = self.font_main.render(good_text, True, t.fg_dark)
            bsurf = self.font_main.render(bad_text, True, t.fg_dark)
            surface.blit(gsurf, gsurf.get_rect(center=good_rect.center))
            surface.blit(bsurf, bsurf.get_rect(center=bad_rect.center))
            text = "Back to Menu" if self.use_english_ui else "メニューに戻る"
            surf = self.font_main.render(text, True, t.fg_dark)
            surface.blit(surf, surf.get_rect(center=back_rect.center))
            if game.rating_feedback:
                self._draw_text(surface, self.font_small, game.rating_feedback, self.width - 560, self.height - 108, (230, 235, 244))

    def render(self, game: QuizGameState) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        if game.game_state == STATE_MENU:
            self._draw_menu(surface, game)
        else:
            self._draw_play(surface, game)
        return surface
