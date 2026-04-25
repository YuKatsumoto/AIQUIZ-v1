"""3D corridor renderer – clean, bright aesthetic.

Renders a white floor, approaching quiz-wall with red/blue doors,
a humanoid player character, and green particles on correct answers.

Requires: moderngl, numpy, pygame
"""

import math
import random
from dataclasses import dataclass

import moderngl
import numpy as np
import pygame

from game.core.constants import STATE_CORRECT, STATE_GAME_OVER, STATE_MENU, STATE_PLAYING
from game.core.game_state import QuizGameState
from game.ui.hud import japanese_font_path

from .math3d import look_at, mat4_mul, perspective, scale, translate, rotate_x, rotate_y, rotate_z

# ---------------------------------------------------------------------------
# Shader source
# ---------------------------------------------------------------------------

_SCENE_VERT = """
#version 330
uniform mat4 u_mvp;
uniform mat4 u_model;
in vec3 in_pos;
in vec3 in_normal;
out vec3 v_world;
out vec3 v_normal;
void main(){
    vec4 w = u_model * vec4(in_pos, 1.0);
    v_world = w.xyz;
    v_normal = mat3(u_model) * in_normal;
    gl_Position = u_mvp * vec4(in_pos, 1.0);
}
"""

_SCENE_FRAG = """
#version 330
uniform vec3 u_color;
uniform vec3 u_eye;
uniform vec3 u_fog_col;
uniform float u_fog_near;
uniform float u_fog_far;
uniform float u_emissive;

// lights
uniform vec3 u_dlight_dir;
uniform vec3 u_dlight_col;
uniform vec3 u_plight_pos;
uniform vec3 u_plight_col;

in vec3 v_world;
in vec3 v_normal;
out vec4 frag;

void main(){
    vec3 n = normalize(v_normal);
    vec3 V = normalize(u_eye - v_world);

    // directional light
    vec3 L = normalize(-u_dlight_dir);
    float NdotL = max(dot(n, L), 0.0);
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(n, H), 0.0), 32.0);

    // point light
    vec3 pL = normalize(u_plight_pos - v_world);
    float pNdotL = max(dot(n, pL), 0.0);
    float d = length(u_plight_pos - v_world);
    float att = 1.0 / (1.0 + d * 0.06 + d * d * 0.012);

    // bright ambient for clean look
    vec3 ambient = vec3(0.30, 0.32, 0.35);
    vec3 col = u_color * (ambient + u_dlight_col * NdotL + u_plight_col * pNdotL * att)
               + spec * 0.25 + u_color * u_emissive;

    // fog
    float fd = length(v_world - u_eye);
    float fog = clamp((fd - u_fog_near) / (u_fog_far - u_fog_near), 0.0, 1.0);
    col = mix(col, u_fog_col, fog);

    frag = vec4(col, 1.0);
}
"""

# Label shader (text on doors)
_LABEL_VERT = """
#version 330
uniform mat4 u_mvp;
uniform mat4 u_model;
in vec3 in_pos;
in vec2 in_uv;
out vec2 v_uv;
out vec3 v_world;
void main(){
    v_uv = in_uv;
    v_world = (u_model * vec4(in_pos, 1.0)).xyz;
    gl_Position = u_mvp * vec4(in_pos, 1.0);
}
"""

_LABEL_FRAG = """
#version 330
uniform sampler2D u_tex;
uniform vec3 u_eye;
uniform vec3 u_fog_col;
uniform float u_fog_near;
uniform float u_fog_far;
in vec2 v_uv;
in vec3 v_world;
out vec4 frag;
void main(){
    vec4 t = texture(u_tex, v_uv);
    if(t.a < 0.05) discard;
    float d = length(v_world - u_eye);
    float fog = clamp((d - u_fog_near) / (u_fog_far - u_fog_near), 0.0, 1.0) * 0.5;
    vec3 c = mix(t.rgb, u_fog_col, fog);
    frag = vec4(c, t.a);
}
"""

# UI overlay shader (text on screen quad)
_UI_VERT = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main(){ v_uv = in_uv; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

_UI_FRAG = """
#version 330
uniform sampler2D u_ui;
in vec2 v_uv;
out vec4 frag;
void main(){ frag = texture(u_ui, v_uv); }
"""

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _cube_vertices() -> np.ndarray:
    """Unit cube: position(3) + normal(3), 36 verts."""
    return np.array([
        # +X
        1,-1,-1, 1,0,0,  1,1,-1, 1,0,0,  1,1,1, 1,0,0,
        1,-1,-1, 1,0,0,  1,1,1, 1,0,0,  1,-1,1, 1,0,0,
        # -X
        -1,-1,1,-1,0,0, -1,1,1,-1,0,0, -1,1,-1,-1,0,0,
        -1,-1,1,-1,0,0, -1,1,-1,-1,0,0, -1,-1,-1,-1,0,0,
        # +Y
        -1,1,-1, 0,1,0, -1,1,1, 0,1,0,  1,1,1, 0,1,0,
        -1,1,-1, 0,1,0,  1,1,1, 0,1,0,  1,1,-1, 0,1,0,
        # -Y
        -1,-1,1, 0,-1,0,-1,-1,-1,0,-1,0, 1,-1,-1,0,-1,0,
        -1,-1,1, 0,-1,0, 1,-1,-1,0,-1,0, 1,-1,1, 0,-1,0,
        # +Z
        -1,-1,1, 0,0,1,  1,-1,1, 0,0,1,  1,1,1, 0,0,1,
        -1,-1,1, 0,0,1,  1,1,1, 0,0,1, -1,1,1, 0,0,1,
        # -Z
        1,-1,-1, 0,0,-1,-1,-1,-1,0,0,-1,-1,1,-1,0,0,-1,
        1,-1,-1, 0,0,-1,-1,1,-1, 0,0,-1, 1,1,-1, 0,0,-1,
    ], dtype="f4")


def _label_quad() -> np.ndarray:
    """Quad facing -Z: position(3) + uv(2), 6 verts."""
    return np.array([
         1,-1,0, 0,0,
        -1,-1,0, 1,0,
        -1, 1,0, 1,1,
         1,-1,0, 0,0,
        -1, 1,0, 1,1,
         1, 1,0, 0,1,
    ], dtype="f4")


def _screen_quad() -> np.ndarray:
    return np.array([
        -1,-1, 0,0,  1,-1, 1,0,  1,1, 1,1,
        -1,-1, 0,0,  1,1, 1,1, -1,1, 0,1,
    ], dtype="f4")

# ---------------------------------------------------------------------------
# Simple particle
# ---------------------------------------------------------------------------

@dataclass
class _Particle:
    x: float; y: float; z: float
    vx: float; vy: float; vz: float
    life: float = 1.0
    decay: float = 1.8
    r: float = 0.2; g: float = 1.0; b: float = 0.4
    size: float = 0.18

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LABEL_W, _LABEL_H = 512, 128
_BG_COLOR = (0.82, 0.85, 0.90)       # bright blue-gray background
_FOG_COLOR = _BG_COLOR
_FOG_NEAR = 18.0
_FOG_FAR = 80.0

# Player colors (warm orange for P1)
_PLAYER_BODY = (0.95, 0.55, 0.20)
_PLAYER_HEAD = (0.95, 0.65, 0.35)
_PLAYER_LIMB = (0.85, 0.48, 0.18)

# Player 2 colors (cool cyan/teal)
_P2_BODY = (0.20, 0.65, 0.90)
_P2_HEAD = (0.30, 0.75, 0.95)
_P2_LIMB = (0.15, 0.55, 0.80)

# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class Renderer3D:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        # --- Shader Programs ---
        self.scene_prog = self.ctx.program(
            vertex_shader=_SCENE_VERT, fragment_shader=_SCENE_FRAG)
        self.label_prog = self.ctx.program(
            vertex_shader=_LABEL_VERT, fragment_shader=_LABEL_FRAG)
        self.ui_prog = self.ctx.program(
            vertex_shader=_UI_VERT, fragment_shader=_UI_FRAG)

        # --- Vertex Arrays ---
        cb = self.ctx.buffer(_cube_vertices().tobytes())
        self.cube_vao = self.ctx.vertex_array(
            self.scene_prog, [(cb, "3f 3f", "in_pos", "in_normal")])

        lb = self.ctx.buffer(_label_quad().tobytes())
        self.label_vao = self.ctx.vertex_array(
            self.label_prog, [(lb, "3f 2f", "in_pos", "in_uv")])

        sq = self.ctx.buffer(_screen_quad().tobytes())
        self.ui_vao = self.ctx.vertex_array(
            self.ui_prog, [(sq, "2f 2f", "in_pos", "in_uv")])

        # --- UI overlay texture ---
        self.ui_tex = self.ctx.texture((width, height), 4)
        self.ui_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        # --- Label textures ---
        self.label_tex_l = self.ctx.texture((_LABEL_W, _LABEL_H), 4)
        self.label_tex_r = self.ctx.texture((_LABEL_W, _LABEL_H), 4)
        self.label_tex_2 = self.ctx.texture((_LABEL_W, _LABEL_H), 4)
        self.label_tex_3 = self.ctx.texture((_LABEL_W, _LABEL_H), 4)
        self.label_tex_l.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.label_tex_r.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.label_tex_2.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.label_tex_3.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._last_quiz_q: int = 0  # cache key: id(quiz_object)

        # --- Font for door labels ---
        jf = japanese_font_path()
        self._label_font = pygame.font.Font(jf if jf else None, 32)

        # --- Particles ---
        self._particles: list[_Particle] = []
        self._prev_correct_flash = 0.0
        self._prev_wrong_flash = 0.0

        # --- Time ---
        self._t = 0.0

    # ---- Resize management ----

    def resize(self, width: int, height: int):
        if width == self.width and height == self.height:
            return
        self.width = max(1, width)
        self.height = max(1, height)
        self.ui_tex.release()
        self.ui_tex = self.ctx.texture((self.width, self.height), 4)
        self.ui_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.ctx.viewport = (0, 0, self.width, self.height)

    # ---- Safe uniform setter ----

    def _set(self, prog, name, value):
        """Safely set a uniform (no-op if optimised away by GLSL compiler)."""
        if name in prog:
            if isinstance(value, bytes):
                prog[name].write(value)
            else:
                prog[name].value = value

    # ---- Camera ----

    def _camera(self, game: QuizGameState):
        bob = math.sin(self._t * 1.2) * 0.04

        if game.num_players >= 2:
            # === 2-PLAYER ===
            all_dead = not game.p1_alive and not game.p2_alive
            if all_dead and game.game_over_timer > 0:
                # Zoom out + shake for 2P
                t = min(1.0, game.game_over_timer * 0.5)
                ease_t = 1.0 - (1.0 - t)**3
                dist_z = -9.0 - ease_t * 10.0
                
                # 振動（最初激しく、徐々に収まる）
                decay_shake = max(0.0, 1.0 - game.game_over_timer * 0.8) * 1.5
                sx = (random.random() - 0.5) * decay_shake
                sy = (random.random() - 0.5) * decay_shake
                
                eye = np.array([
                    sx,
                    4.5 + bob + ease_t * 6.0 + sy,
                    game.player_z + dist_z
                ], dtype=np.float32)
                
                ctr = np.array([
                    sx * 0.5,
                    1.0 + ease_t * 2.0 + sy * 0.5,
                    game.player_z + 8.0 * (1.0 - ease_t)
                ], dtype=np.float32)
            else:
                eye = np.array([0.0, 4.5 + bob, game.player_z - 9.0], dtype=np.float32)
                ctr = np.array([0.0, 1.0, game.player_z + 8.0], dtype=np.float32)
            fov = 50.0
        else:
            # === 1-PLAYER ===
            all_dead = not game.p1_alive
            if all_dead and game.game_over_timer > 0:
                # Zoom out + shake for 1P
                t = min(1.0, game.game_over_timer * 0.5)
                ease_t = 1.0 - (1.0 - t)**3
                dist = ease_t * 16.0
                
                # 振動（最初激しく、徐々に収まる）
                decay_shake = max(0.0, 1.0 - game.game_over_timer * 0.8) * 1.5
                sx = (random.random() - 0.5) * decay_shake
                sy = (random.random() - 0.5) * decay_shake
                
                eye = np.array([
                    game.player_x + sx,
                    1.2 + bob + ease_t * 6.0 + sy,
                    game.player_z - dist
                ], dtype=np.float32)
                
                ctr = np.array([
                    game.player_x + sx * 0.5,
                    1.2 + ease_t * 1.5 + sy * 0.5,
                    game.player_z + 10.0 * (1.0 - ease_t)
                ], dtype=np.float32)
            else:
                yaw = game.camera_yaw
                pitch = game.camera_pitch
                dx = math.sin(yaw) * math.cos(pitch)
                dy = math.sin(pitch)
                dz = math.cos(yaw) * math.cos(pitch)
                eye = np.array([game.player_x, 1.2 + bob, game.player_z], dtype=np.float32)
                ctr = eye + np.array([dx, dy, dz], dtype=np.float32) * 10.0
            fov = 44.0

        # Apply camera shake
        if game.camera_shake > 0.0:
            shake_ox = (random.random() - 0.5) * game.camera_shake
            shake_oy = (random.random() - 0.5) * game.camera_shake
            shake_oz = (random.random() - 0.5) * game.camera_shake
            eye[0] += shake_ox
            eye[1] += shake_oy
            eye[2] += shake_oz
            ctr[0] += shake_ox * 0.5
            ctr[1] += shake_oy * 0.5

        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        view = look_at(eye, ctr, up)
        proj = perspective(
            fov, self.width / max(1.0, float(self.height)), 0.1, 160.0)
        return eye, view, proj

    # ---- Draw cube helper ----

    def _cube(self, vw, pr, eye, pos, sc, col, em=0.0, rot=None):
        m = mat4_mul(translate(pos), rot if rot is not None else np.identity(4, dtype=np.float32))
        model = mat4_mul(m, scale(sc))
        mvp = mat4_mul(pr, mat4_mul(vw, model))
        sp = self.scene_prog
        self._set(sp, "u_model", model.T.tobytes())
        self._set(sp, "u_mvp", mvp.T.tobytes())
        self._set(sp, "u_color", col)
        self._set(sp, "u_eye", tuple(float(v) for v in eye))
        self._set(sp, "u_fog_col", _FOG_COLOR)
        self._set(sp, "u_fog_near", _FOG_NEAR)
        self._set(sp, "u_fog_far", _FOG_FAR)
        self._set(sp, "u_emissive", float(em))
        self._set(sp, "u_dlight_dir", (-0.3, -1.0, -0.4))
        self._set(sp, "u_dlight_col", (0.90, 0.92, 0.95))
        self._set(sp, "u_plight_pos", (0.0, 3.0, -6.0))
        self._set(sp, "u_plight_col", (0.40, 0.42, 0.50))
        self.cube_vao.render()

    # ---- Floor ----

    def _draw_floor(self, eye, vw, pr, player_z: float):
        # Distinct dark floor that follows the player
        self._cube(vw, pr, eye,
                   (0, -1.3, player_z + 12), (12, 0.1, 72), (0.35, 0.35, 0.35))

    # ---- Quiz wall & doors ----

    def _draw_wall_doors(self, game, eye, vw, pr, wz: float):
        t = game.tuning
        c = self._cube

        # Gray wall slab
        c(vw, pr, eye, (0, 0.45, wz), (14.0, 3.6, 0.55), (0.50, 0.50, 0.50))

        if game.num_choices == 4:
            # 4 doors: A(blue), B(green), C(orange), D(red)
            door_colors = [
                (0.10, 0.55, 0.95),   # A - Blue
                (0.15, 0.75, 0.30),   # B - Green
                (0.95, 0.60, 0.10),   # C - Orange
                (0.90, 0.15, 0.15),   # D - Red
            ]
            for i, dx in enumerate(t.door4_xs):
                c(vw, pr, eye, (dx, 0.18, wz),
                  (1.45, 2.2, 0.60), door_colors[i])
        else:
            # 2 doors: Blue left, Red right
            c(vw, pr, eye, (t.left_door_x, 0.18, wz),
              (1.8, 2.2, 0.60), (0.10, 0.60, 0.95))
            c(vw, pr, eye, (t.right_door_x, 0.18, wz),
              (1.8, 2.2, 0.60), (0.90, 0.15, 0.10))

    # ---- Humanoid player (6-part block person) ----

    def _draw_player_alive(self, game, eye, vw, pr, px, pz,
                           body_col, head_col, limb_col, walk_phase: float = 0.0):
        """Draw a walking humanoid at (px, pz) with given colors."""
        by = -1.2  # base Y (just above floor)
        c = self._cube
        # Walking animation: swing legs & arms using sin
        swing = math.sin(walk_phase) * 0.35

        # Left Leg
        leg_rot_l = rotate_x(swing)
        c(vw, pr, eye, (px - 0.22, by + 0.45, pz), (0.18, 0.45, 0.18), limb_col, rot=leg_rot_l)
        # Right Leg
        leg_rot_r = rotate_x(-swing)
        c(vw, pr, eye, (px + 0.22, by + 0.45, pz), (0.18, 0.45, 0.18), limb_col, rot=leg_rot_r)
        # Torso
        c(vw, pr, eye, (px, by + 1.20, pz), (0.38, 0.45, 0.22), body_col)
        # Left Arm
        arm_rot_l = rotate_x(-swing * 0.7)
        c(vw, pr, eye, (px - 0.52, by + 1.15, pz), (0.12, 0.40, 0.14), limb_col, rot=arm_rot_l)
        # Right Arm
        arm_rot_r = rotate_x(swing * 0.7)
        c(vw, pr, eye, (px + 0.52, by + 1.15, pz), (0.12, 0.40, 0.14), limb_col, rot=arm_rot_r)
        # Head
        c(vw, pr, eye, (px, by + 1.87, pz), (0.22, 0.22, 0.22), head_col)

    def _draw_player_exploding(self, eye, vw, pr, px, pz, timer,
                               body_col, head_col, limb_col):
        """Draw exploding humanoid parts."""
        by = -1.2
        c = self._cube

        def _explode(ox, oy, oz, vx, vy, vz, rvx, rvy, rvz):
            ey = oy + vy * timer - 0.5 * 15.0 * timer * timer
            ey = max(by + 0.1, ey)
            ex = ox + vx * timer
            ez = oz + vz * timer
            rx = rvx * timer
            ry = rvy * timer
            rz = rvz * timer
            rot_mat = mat4_mul(rotate_z(rz), mat4_mul(rotate_y(ry), rotate_x(rx)))
            return (ex, ey, ez), rot_mat

        # Left Leg
        p, r = _explode(px - 0.22, by + 0.45, pz, -3.0, 8.0, -2.0, 3.0, 1.0, -2.0)
        c(vw, pr, eye, p, (0.18, 0.45, 0.18), limb_col, rot=r)
        # Right Leg
        p, r = _explode(px + 0.22, by + 0.45, pz, 3.0, 7.5, 2.0, -2.5, 2.0, 1.5)
        c(vw, pr, eye, p, (0.18, 0.45, 0.18), limb_col, rot=r)
        # Torso
        p, r = _explode(px, by + 1.20, pz, 0.5, 6.0, 4.0, 1.0, -1.5, 0.5)
        c(vw, pr, eye, p, (0.38, 0.45, 0.22), body_col, rot=r)
        # Left Arm
        p, r = _explode(px - 0.52, by + 1.15, pz, -6.0, 9.0, 1.0, -4.0, -2.0, 3.0)
        c(vw, pr, eye, p, (0.12, 0.40, 0.14), limb_col, rot=r)
        # Right Arm
        p, r = _explode(px + 0.52, by + 1.15, pz, 5.0, 10.0, -1.5, 2.0, 4.0, -1.0)
        c(vw, pr, eye, p, (0.12, 0.40, 0.14), limb_col, rot=r)
        # Head
        p, r = _explode(px, by + 1.87, pz, -1.0, 12.0, 3.0, 5.0, 3.0, 2.0)
        c(vw, pr, eye, p, (0.22, 0.22, 0.22), head_col, rot=r)

    def _draw_players(self, game, eye, vw, pr):
        """Draw all player models (alive = walking, dead = exploding)."""
        pz = game.player_z
        walk_phase = self._t * 8.0  # walking speed

        # --- Player 1 ---
        if game.p1_alive:
            self._draw_player_alive(game, eye, vw, pr,
                                    game.player_x, pz,
                                    _PLAYER_BODY, _PLAYER_HEAD, _PLAYER_LIMB,
                                    walk_phase if game.game_state == STATE_PLAYING else 0.0)
        elif game.game_over_timer > 0:
            self._draw_player_exploding(eye, vw, pr,
                                        game.player_x, pz, game.game_over_timer,
                                        _PLAYER_BODY, _PLAYER_HEAD, _PLAYER_LIMB)

        # --- Player 2 ---
        if game.num_players >= 2:
            if game.p2_alive:
                self._draw_player_alive(game, eye, vw, pr,
                                        game.player2_x, pz,
                                        _P2_BODY, _P2_HEAD, _P2_LIMB,
                                        walk_phase * 1.1 if game.game_state == STATE_PLAYING else 0.0)
            elif game.player2_game_over_timer > 0:
                self._draw_player_exploding(eye, vw, pr,
                                            game.player2_x, pz, game.player2_game_over_timer,
                                            _P2_BODY, _P2_HEAD, _P2_LIMB)

    # ---- Door labels (white bg, black text) ----

    def _render_label_surf(self, text: str,
                           accent: tuple[int, int, int]) -> pygame.Surface:
        surf = pygame.Surface((_LABEL_W, _LABEL_H), pygame.SRCALPHA)
        bg = pygame.Rect(4, 4, _LABEL_W - 8, _LABEL_H - 8)
        # White background
        pygame.draw.rect(surf, (245, 245, 245, 240), bg, border_radius=12)
        # Colored border
        pygame.draw.rect(surf, accent, bg, width=3, border_radius=12)
        # Black text
        lines = self._wrap_text(text, self._label_font, _LABEL_W - 40)
        total_h = sum(self._label_font.get_height() for _ in lines)
        y = (_LABEL_H - total_h) // 2
        for line in lines:
            ts = self._label_font.render(line, True, (20, 20, 20))
            surf.blit(ts, ((_LABEL_W - ts.get_width()) // 2, y))
            y += self._label_font.get_height()
        return surf

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font,
                   max_w: int) -> list[str]:
        if font.size(text)[0] <= max_w:
            return [text]
        lines: list[str] = []
        current = ""
        for ch in text:
            test = current + ch
            if font.size(test)[0] > max_w:
                if current:
                    lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
        return lines or [text]

    def _update_labels(self, game: QuizGameState):
        q = game.current_quiz
        key = id(q)   # unique per quiz object – no false cache hits
        if key == self._last_quiz_q:
            return
        self._last_quiz_q = key
        if not q:
            blank = pygame.Surface((_LABEL_W, _LABEL_H), pygame.SRCALPHA)
            data = pygame.image.tobytes(blank, "RGBA", True)
            self.label_tex_l.write(data)
            self.label_tex_r.write(data)
            self.label_tex_2.write(data)
            self.label_tex_3.write(data)
            return

        if game.num_choices == 4:
            # 4 doors: A(blue), B(green), C(orange), D(red)
            door_colors_4 = [
                (25, 140, 240),   # A - Blue
                (38, 190, 76),    # B - Green
                (240, 150, 25),   # C - Orange
                (230, 40, 40),    # D - Red
            ]
            labels_4 = ["A", "B", "C", "D"]
            textures = [self.label_tex_l, self.label_tex_r, self.label_tex_2, self.label_tex_3]
            for i in range(4):
                choice_text = q.c[i] if i < len(q.c) else "?"
                label = f"{labels_4[i]}. {choice_text}"
                surf = self._render_label_surf(label, door_colors_4[i])
                textures[i].write(pygame.image.tobytes(surf, "RGBA", True))
        else:
            # 2 doors: Blue left, Red right
            left_surf = self._render_label_surf(q.c[0], (25, 150, 240))
            right_surf = self._render_label_surf(q.c[1], (230, 40, 25))
            self.label_tex_l.write(
                pygame.image.tobytes(left_surf, "RGBA", True))
            self.label_tex_r.write(
                pygame.image.tobytes(right_surf, "RGBA", True))

    def _draw_labels(self, game: QuizGameState, eye, vw, pr):
        if not game.current_quiz or game.game_state == STATE_MENU:
            return
        t = game.tuning
        wz = game.wall_z

        self.ctx.disable(moderngl.CULL_FACE)
        lp = self.label_prog
        self._set(lp, "u_eye", tuple(float(v) for v in eye))
        self._set(lp, "u_fog_col", _FOG_COLOR)
        self._set(lp, "u_fog_near", _FOG_NEAR)
        self._set(lp, "u_fog_far", _FOG_FAR)

        if game.num_choices == 4:
            lw, lh = 1.35, 0.44
            textures = [self.label_tex_l, self.label_tex_r, self.label_tex_2, self.label_tex_3]
            for i, dx in enumerate(t.door4_xs):
                model = mat4_mul(
                    translate((dx, 0.18, wz - 0.65)), scale((lw, lh, 1.0)))
                mvp = mat4_mul(pr, mat4_mul(vw, model))
                self._set(lp, "u_model", model.T.tobytes())
                self._set(lp, "u_mvp", mvp.T.tobytes())
                textures[i].use(location=2)
                self._set(lp, "u_tex", 2)
                self.label_vao.render()
        else:
            lw, lh = 1.6, 0.48
            for _side, tex, dx in ((0, self.label_tex_l, t.left_door_x),
                                    (1, self.label_tex_r, t.right_door_x)):
                model = mat4_mul(
                    translate((dx, 0.18, wz - 0.65)), scale((lw, lh, 1.0)))
                mvp = mat4_mul(pr, mat4_mul(vw, model))
                self._set(lp, "u_model", model.T.tobytes())
                self._set(lp, "u_mvp", mvp.T.tobytes())
                tex.use(location=2)
                self._set(lp, "u_tex", 2)
                self.label_vao.render()

        self.ctx.enable(moderngl.CULL_FACE)

    # ---- Particles (green only, on correct) ----

    def _spawn_correct(self, x: float, y: float, z: float):
        # Colorful celebration fountain
        for _ in range(100):
            p = _Particle(x, y + 1.0, z,
                          (random.random() - 0.5) * 8.0,
                          random.random() * 15.0 + 5.0,
                          (random.random() - 0.5) * 8.0)
            
            # Gold / Yellow / Bright Cyan colors
            color_type = random.random()
            if color_type < 0.5:
                p.r, p.g, p.b = 1.0, 0.9, 0.2  # Gold
            elif color_type < 0.8:
                p.r, p.g, p.b = 0.2, 1.0, 0.5  # Green
            else:
                p.r, p.g, p.b = 0.3, 0.8, 1.0  # Cyan
                
            p.decay = 0.6 + random.random() * 0.4
            p.size = 0.15 + random.random() * 0.2
            self._particles.append(p)

    def _spawn_explosion(self, x: float, y: float, z: float):
        # Increased particle count and fiery speed
        for _ in range(250):
            p = _Particle(x, y + 0.5, z,
                          (random.random() - 0.5) * 30.0,
                          random.random() * 20.0 + 2.0,
                          (random.random() - 0.5) * 30.0)
            
            # Fiery colors: bright red-orange
            p.r = 1.0
            p.g = random.random() * 0.6 + 0.2
            p.b = random.random() * 0.2
            
            p.decay = 0.5 + random.random() * 1.5
            p.size = 0.2 + random.random() * 0.6
            self._particles.append(p)

    def _update_particles(self, dt: float, game: QuizGameState):
        # Spawn on correct transition only
        if game.correct_flash > 0.8 and self._prev_correct_flash <= 0.8:
            self._spawn_correct(game.player_x, 0.0, game.tuning.hit_z)
        self._prev_correct_flash = game.correct_flash

        # Spawn on wrong transition
        if game.wrong_flash > 0.8 and self._prev_wrong_flash <= 0.8:
            self._spawn_explosion(game.player_x, 0.0, game.player_z)
        self._prev_wrong_flash = game.wrong_flash

        alive: list[_Particle] = []
        for p in self._particles:
            p.life -= p.decay * dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy -= 6.0 * dt  # gravity
            p.z += p.vz * dt
            alive.append(p)
        self._particles = alive

    def _draw_particles(self, eye, vw, pr):
        for p in self._particles:
            em = max(0.0, p.life) * 0.8
            self._cube(vw, pr, eye,
                       (p.x, p.y, p.z),
                       (p.size, p.size, p.size),
                       (p.r, p.g, p.b), em=em)

    # ---- Scene orchestration ----

    def _draw_world(self, game: QuizGameState):
        eye, vw, pr = self._camera(game)
        self._draw_floor(eye, vw, pr, game.player_z)

        # Draw player models:
        # - 2P mode: always show both player models (walking or exploding)
        # - 1P mode: only show during explosion (game over)
        if game.game_state != STATE_MENU:
            if game.num_players >= 2:
                self._draw_players(game, eye, vw, pr)
            elif game.game_state == STATE_GAME_OVER and game.game_over_timer > 0:
                # 1P: only draw the exploding body during game over
                self._draw_players(game, eye, vw, pr)

        if game.game_state != STATE_MENU:
            # Draw current wall + upcoming walls that are within view
            t = game.tuning
            for i in range(4):  # draw up to 4 walls ahead
                idx = game.current_wall_index + i
                wz = t.wall_start_z + idx * t.wall_spacing
                # Only draw if wall is ahead of player
                if wz > game.player_z - 2.0:
                    self._draw_wall_doors(game, eye, vw, pr, wz)
            self._update_labels(game)
            self._draw_labels(game, eye, vw, pr)
        self._draw_particles(eye, vw, pr)

    def _upload_ui(self, ui_surface: pygame.Surface):
        """Upload the HUD surface to GPU. GPU LINEAR filter handles any size mismatch."""
        sw, sh = ui_surface.get_width(), ui_surface.get_height()
        # Recreate texture only when HUD size changes (rare: only on resize)
        if self.ui_tex.size != (sw, sh):
            self.ui_tex.release()
            self.ui_tex = self.ctx.texture((sw, sh), 4)
            self.ui_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.ui_tex.write(pygame.image.tobytes(ui_surface, "RGBA", True))

    # ---- Main entry ----

    def render(self, game: QuizGameState, ui_surface: pygame.Surface,
               dt: float):
        self._t += dt
        self._update_particles(dt, game)
        self.ctx.viewport = (0, 0, self.width, self.height)

        # Draw scene directly to the default framebuffer (no FBO indirection)
        self.ctx.screen.use()
        self.ctx.enable(
            moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        if game.game_state == STATE_MENU:
            self.ctx.clear(0.96, 0.94, 0.91, 1.0, depth=1.0)
        else:
            self.ctx.clear(*_BG_COLOR, 1.0, depth=1.0)
        self._draw_world(game)

        # UI overlay (drawn on top, no depth test)
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self._upload_ui(ui_surface)
        self.ui_tex.use(location=1)
        self._set(self.ui_prog, "u_ui", 1)
        self.ui_vao.render()
        self.ctx.enable(
            moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
