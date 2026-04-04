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

from .math3d import look_at, mat4_mul, perspective, scale, translate

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

# Post-process: simple bloom + vignette + correct/wrong flash
_POST_VERT = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main(){ v_uv = in_uv; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

_POST_FRAG = """
#version 330
uniform sampler2D u_scene;
uniform float u_time;
uniform float u_correct;
uniform float u_wrong;
in vec2 v_uv;
out vec4 frag;

vec3 bloom(vec2 uv){
    vec2 tx = 1.0 / vec2(textureSize(u_scene, 0));
    vec3 c = texture(u_scene, uv).rgb;
    vec3 s = c * 0.35;
    for(int i = 1; i <= 3; i++){
        float w = 0.10 / float(i);
        float o = float(i) * 1.5;
        s += texture(u_scene, uv + vec2(tx.x * o, 0)).rgb * w;
        s += texture(u_scene, uv - vec2(tx.x * o, 0)).rgb * w;
        s += texture(u_scene, uv + vec2(0, tx.y * o)).rgb * w;
        s += texture(u_scene, uv - vec2(0, tx.y * o)).rgb * w;
    }
    return c + max(s - vec3(0.60), 0.0) * 1.5;
}

void main(){
    vec3 col = bloom(v_uv);

    // vignette (subtle)
    float dc = length(v_uv - 0.5);
    col *= smoothstep(0.85, 0.30, dc);

    // correct = green pulse
    col += vec3(0.10, 0.75, 0.25) * u_correct * 0.15
           * (0.7 + 0.3 * sin(u_time * 12.0));

    // wrong = red tint
    col += vec3(0.80, 0.10, 0.10) * u_wrong * 0.15;

    frag = vec4(col, 1.0);
}
"""

_UI_VERT = _POST_VERT

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
         1,-1,0, 1,0,
        -1,-1,0, 0,0,
        -1, 1,0, 0,1,
         1,-1,0, 1,0,
        -1, 1,0, 0,1,
         1, 1,0, 1,1,
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

# Player colors (warm orange for visibility)
_PLAYER_BODY = (0.95, 0.55, 0.20)
_PLAYER_HEAD = (0.95, 0.65, 0.35)
_PLAYER_LIMB = (0.85, 0.48, 0.18)

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
        self.post_prog = self.ctx.program(
            vertex_shader=_POST_VERT, fragment_shader=_POST_FRAG)
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
        self.post_vao = self.ctx.vertex_array(
            self.post_prog, [(sq, "2f 2f", "in_pos", "in_uv")])
        self.ui_vao = self.ctx.vertex_array(
            self.ui_prog, [(sq, "2f 2f", "in_pos", "in_uv")])

        # --- Framebuffer ---
        self._create_fbos(width, height)

        # --- Label textures ---
        self.label_tex_l = self.ctx.texture((_LABEL_W, _LABEL_H), 4)
        self.label_tex_r = self.ctx.texture((_LABEL_W, _LABEL_H), 4)
        self.label_tex_l.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.label_tex_r.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._last_quiz_q: str = ""

        # --- Font for door labels ---
        jf = japanese_font_path()
        self._label_font = pygame.font.Font(jf if jf else None, 32)

        # --- Particles ---
        self._particles: list[_Particle] = []
        self._prev_correct_flash = 0.0

        # --- Time ---
        self._t = 0.0

    # ---- FBO management ----

    def _create_fbos(self, w: int, h: int):
        self.scene_col = self.ctx.texture((w, h), 4)
        self.scene_dep = self.ctx.depth_texture((w, h))
        self.scene_fbo = self.ctx.framebuffer(self.scene_col, self.scene_dep)
        self.scene_col.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.ui_tex = self.ctx.texture((w, h), 4)
        self.ui_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

    def resize(self, width: int, height: int):
        if width == self.width and height == self.height:
            return
        self.width = max(1, width)
        self.height = max(1, height)
        for obj in (self.scene_col, self.scene_dep, self.scene_fbo, self.ui_tex):
            obj.release()
        self._create_fbos(self.width, self.height)
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
        # Subtle idle bob only — no camera shake per user spec
        bob = math.sin(self._t * 1.2) * 0.08
        eye = np.array([0.0, 6.3 + bob, -19.0], dtype=np.float32)
        ctr = np.array([0.0, 0.0, game.tuning.hit_z + 12.0], dtype=np.float32)
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        view = look_at(eye, ctr, up)
        proj = perspective(
            44.0, self.width / max(1.0, float(self.height)), 0.1, 160.0)
        return eye, view, proj

    # ---- Draw cube helper ----

    def _cube(self, vw, pr, eye, pos, sc, col, em=0.0):
        model = mat4_mul(translate(pos), scale(sc))
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

    def _draw_floor(self, eye, vw, pr):
        # White floor — no decoration
        self._cube(vw, pr, eye,
                   (0, -1.3, 12), (12, 0.1, 72), (0.92, 0.92, 0.92))

    # ---- Quiz wall & doors ----

    def _draw_wall_doors(self, game, eye, vw, pr):
        t = game.tuning
        wz = game.wall_z
        c = self._cube

        # White wall slab
        c(vw, pr, eye, (0, 0.45, wz), (11.6, 3.6, 0.55), (0.85, 0.85, 0.88))

        # Red left door (cutout)
        c(vw, pr, eye, (t.left_door_x, 0.18, wz),
          (2.7, 2.5, 0.60), (0.85, 0.20, 0.15))

        # Blue right door (cutout)
        c(vw, pr, eye, (t.right_door_x, 0.18, wz),
          (2.7, 2.5, 0.60), (0.15, 0.30, 0.85))

    # ---- Humanoid player (6-part block person) ----

    def _draw_player(self, game, eye, vw, pr):
        px = game.player_x
        hz = game.tuning.hit_z
        by = -1.2  # base Y (just above floor)
        c = self._cube

        # Legs (2)
        c(vw, pr, eye, (px - 0.22, by + 0.45, hz),
          (0.18, 0.45, 0.18), _PLAYER_LIMB)
        c(vw, pr, eye, (px + 0.22, by + 0.45, hz),
          (0.18, 0.45, 0.18), _PLAYER_LIMB)

        # Torso
        c(vw, pr, eye, (px, by + 1.20, hz),
          (0.38, 0.45, 0.22), _PLAYER_BODY)

        # Arms (2)
        c(vw, pr, eye, (px - 0.52, by + 1.15, hz),
          (0.12, 0.40, 0.14), _PLAYER_LIMB)
        c(vw, pr, eye, (px + 0.52, by + 1.15, hz),
          (0.12, 0.40, 0.14), _PLAYER_LIMB)

        # Head
        c(vw, pr, eye, (px, by + 1.87, hz),
          (0.22, 0.22, 0.22), _PLAYER_HEAD)

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
        key = q.q if q else ""
        if key == self._last_quiz_q:
            return
        self._last_quiz_q = key
        if not q:
            blank = pygame.Surface((_LABEL_W, _LABEL_H), pygame.SRCALPHA)
            data = pygame.image.tobytes(blank, "RGBA", True)
            self.label_tex_l.write(data)
            self.label_tex_r.write(data)
            return
        # Red border for left door, blue for right
        left_surf = self._render_label_surf(q.c[0], (200, 50, 40))
        right_surf = self._render_label_surf(q.c[1], (40, 70, 200))
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

        lw, lh = 2.4, 0.72
        for _side, tex, dx in ((0, self.label_tex_l, t.left_door_x),
                                (1, self.label_tex_r, t.right_door_x)):
            model = mat4_mul(
                translate((dx, 0.35, wz - 0.40)), scale((lw, lh, 1.0)))
            mvp = mat4_mul(pr, mat4_mul(vw, model))
            self._set(lp, "u_model", model.T.tobytes())
            self._set(lp, "u_mvp", mvp.T.tobytes())
            tex.use(location=2)
            self._set(lp, "u_tex", 2)
            self.label_vao.render()

        self.ctx.enable(moderngl.CULL_FACE)

    # ---- Particles (green only, on correct) ----

    def _spawn_correct(self, x: float, y: float, z: float):
        for _ in range(28):
            self._particles.append(_Particle(
                x=x + random.uniform(-0.6, 0.6),
                y=y + random.uniform(-0.3, 0.5),
                z=z + random.uniform(-0.5, 0.5),
                vx=random.uniform(-3.0, 3.0),
                vy=random.uniform(1.5, 5.5),
                vz=random.uniform(-2.0, 2.0),
                r=0.2, g=1.0, b=0.4,
                size=random.uniform(0.10, 0.28),
                decay=random.uniform(1.4, 2.8),
            ))

    def _update_particles(self, dt: float, game: QuizGameState):
        # Spawn on correct transition only
        if game.correct_flash > 0.8 and self._prev_correct_flash <= 0.8:
            self._spawn_correct(game.player_x, 0.0, game.tuning.hit_z)
        self._prev_correct_flash = game.correct_flash

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
        self._draw_floor(eye, vw, pr)
        self._draw_player(game, eye, vw, pr)
        if game.game_state != STATE_MENU:
            self._draw_wall_doors(game, eye, vw, pr)
            self._update_labels(game)
            self._draw_labels(game, eye, vw, pr)
        self._draw_particles(eye, vw, pr)

    def _upload_ui(self, ui_surface: pygame.Surface):
        if (ui_surface.get_width() != self.width
                or ui_surface.get_height() != self.height):
            ui_surface = pygame.transform.smoothscale(
                ui_surface, (self.width, self.height))
        self.ui_tex.write(pygame.image.tobytes(ui_surface, "RGBA", True))

    # ---- Main entry ----

    def render(self, game: QuizGameState, ui_surface: pygame.Surface,
               dt: float):
        self._t += dt
        self._update_particles(dt, game)
        self.ctx.viewport = (0, 0, self.width, self.height)

        # Scene pass
        self.scene_fbo.use()
        self.ctx.enable(
            moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        if game.game_state == STATE_MENU:
            self.ctx.clear(0.96, 0.94, 0.91, 1.0, depth=1.0)
        else:
            self.ctx.clear(*_BG_COLOR, 1.0, depth=1.0)
        self._draw_world(game)

        # Post-process to screen
        self.ctx.screen.use()
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.scene_col.use(location=0)
        pp = self.post_prog
        self._set(pp, "u_scene", 0)
        self._set(pp, "u_time", self._t)
        self._set(pp, "u_correct", min(1.0, game.correct_flash))
        self._set(pp, "u_wrong", min(1.0, game.wrong_flash))
        self.post_vao.render()

        # UI overlay
        self._upload_ui(ui_surface)
        self.ui_tex.use(location=1)
        self._set(self.ui_prog, "u_ui", 1)
        self.ui_vao.render()
        self.ctx.enable(
            moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
