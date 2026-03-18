import math

import moderngl
import numpy as np
import pygame

from game.core.constants import STATE_MENU
from game.core.game_state import QuizGameState

from .math3d import look_at, mat4_mul, perspective, scale, translate


def _cube_vertices() -> np.ndarray:
    # position.xyz, normal.xyz
    return np.array(
        [
            # +X
            1, -1, -1, 1, 0, 0,
            1, 1, -1, 1, 0, 0,
            1, 1, 1, 1, 0, 0,
            1, -1, -1, 1, 0, 0,
            1, 1, 1, 1, 0, 0,
            1, -1, 1, 1, 0, 0,
            # -X
            -1, -1, 1, -1, 0, 0,
            -1, 1, 1, -1, 0, 0,
            -1, 1, -1, -1, 0, 0,
            -1, -1, 1, -1, 0, 0,
            -1, 1, -1, -1, 0, 0,
            -1, -1, -1, -1, 0, 0,
            # +Y
            -1, 1, -1, 0, 1, 0,
            -1, 1, 1, 0, 1, 0,
            1, 1, 1, 0, 1, 0,
            -1, 1, -1, 0, 1, 0,
            1, 1, 1, 0, 1, 0,
            1, 1, -1, 0, 1, 0,
            # -Y
            -1, -1, 1, 0, -1, 0,
            -1, -1, -1, 0, -1, 0,
            1, -1, -1, 0, -1, 0,
            -1, -1, 1, 0, -1, 0,
            1, -1, -1, 0, -1, 0,
            1, -1, 1, 0, -1, 0,
            # +Z
            -1, -1, 1, 0, 0, 1,
            1, -1, 1, 0, 0, 1,
            1, 1, 1, 0, 0, 1,
            -1, -1, 1, 0, 0, 1,
            1, 1, 1, 0, 0, 1,
            -1, 1, 1, 0, 0, 1,
            # -Z
            1, -1, -1, 0, 0, -1,
            -1, -1, -1, 0, 0, -1,
            -1, 1, -1, 0, 0, -1,
            1, -1, -1, 0, 0, -1,
            -1, 1, -1, 0, 0, -1,
            1, 1, -1, 0, 0, -1,
        ],
        dtype="f4",
    )


class Renderer3D:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        self.scene_program = self.ctx.program(
            vertex_shader="""
                #version 330
                uniform mat4 u_mvp;
                uniform mat4 u_model;
                in vec3 in_pos;
                in vec3 in_normal;
                out vec3 v_world_pos;
                out vec3 v_normal;
                void main() {
                    vec4 world = u_model * vec4(in_pos, 1.0);
                    v_world_pos = world.xyz;
                    v_normal = mat3(u_model) * in_normal;
                    gl_Position = u_mvp * vec4(in_pos, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                uniform vec3 u_color;
                uniform vec3 u_camera_pos;
                uniform vec3 u_dir_light_dir;
                uniform vec3 u_dir_light_color;
                uniform vec3 u_point_light_pos;
                uniform vec3 u_point_light_color;
                uniform float u_emissive;
                in vec3 v_world_pos;
                in vec3 v_normal;
                out vec4 fragColor;
                void main() {
                    vec3 n = normalize(v_normal);
                    vec3 view_dir = normalize(u_camera_pos - v_world_pos);
                    vec3 dir_l = normalize(-u_dir_light_dir);
                    float ndl = max(dot(n, dir_l), 0.0);
                    vec3 diffuse = u_dir_light_color * ndl;

                    vec3 point_dir = normalize(u_point_light_pos - v_world_pos);
                    float pndl = max(dot(n, point_dir), 0.0);
                    float dist = length(u_point_light_pos - v_world_pos);
                    float att = 1.0 / (1.0 + dist * 0.12 + dist * dist * 0.03);
                    vec3 pdiff = u_point_light_color * pndl * att;

                    vec3 half_dir = normalize(dir_l + view_dir);
                    float spec = pow(max(dot(n, half_dir), 0.0), 24.0);

                    vec3 ambient = vec3(0.10, 0.12, 0.18);
                    vec3 base = u_color * (ambient + diffuse + pdiff) + vec3(spec * 0.35);
                    vec3 emissive = u_color * u_emissive;
                    fragColor = vec4(base + emissive, 1.0);
                }
            """,
        )

        self.post_program = self.ctx.program(
            vertex_shader="""
                #version 330
                in vec2 in_pos;
                in vec2 in_uv;
                out vec2 v_uv;
                void main() {
                    v_uv = in_uv;
                    gl_Position = vec4(in_pos, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                uniform sampler2D u_scene;
                uniform float u_time;
                uniform float u_hit_flash;
                in vec2 v_uv;
                out vec4 fragColor;

                vec3 bloomApprox(vec2 uv){
                    vec2 texel = 1.0 / vec2(textureSize(u_scene, 0));
                    vec3 c = texture(u_scene, uv).rgb;
                    vec3 sum = c * 0.40;
                    sum += texture(u_scene, uv + vec2( texel.x, 0.0)).rgb * 0.12;
                    sum += texture(u_scene, uv + vec2(-texel.x, 0.0)).rgb * 0.12;
                    sum += texture(u_scene, uv + vec2(0.0,  texel.y)).rgb * 0.12;
                    sum += texture(u_scene, uv + vec2(0.0, -texel.y)).rgb * 0.12;
                    vec3 threshold = max(sum - vec3(0.72), 0.0);
                    return c + threshold * 1.8;
                }

                void main() {
                    vec3 col = bloomApprox(v_uv);
                    float d = distance(v_uv, vec2(0.5));
                    float vig = smoothstep(0.78, 0.28, d);
                    col *= vig;

                    // hit_flash: correct=green side, wrong=red side
                    vec3 flash_col = mix(vec3(0.25, 0.95, 0.45), vec3(1.0, 0.22, 0.22), step(0.5, u_hit_flash));
                    float flash_amp = abs(sin(u_time * 16.0)) * 0.12;
                    col += flash_col * flash_amp * min(u_hit_flash, 1.0);
                    fragColor = vec4(col, 1.0);
                }
            """,
        )

        self.ui_program = self.ctx.program(
            vertex_shader="""
                #version 330
                in vec2 in_pos;
                in vec2 in_uv;
                out vec2 v_uv;
                void main() {
                    v_uv = in_uv;
                    gl_Position = vec4(in_pos, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                uniform sampler2D u_ui;
                in vec2 v_uv;
                out vec4 fragColor;
                void main() {
                    vec4 c = texture(u_ui, v_uv);
                    fragColor = c;
                }
            """,
        )

        self.cube_vbo = self.ctx.buffer(_cube_vertices().tobytes())
        self.cube_vao = self.ctx.vertex_array(
            self.scene_program,
            [(self.cube_vbo, "3f 3f", "in_pos", "in_normal")],
        )

        screen_quad = np.array(
            [
                -1, -1, 0, 0,
                1, -1, 1, 0,
                1, 1, 1, 1,
                -1, -1, 0, 0,
                1, 1, 1, 1,
                -1, 1, 0, 1,
            ],
            dtype="f4",
        )
        self.quad_vbo = self.ctx.buffer(screen_quad.tobytes())
        self.post_vao = self.ctx.vertex_array(
            self.post_program,
            [(self.quad_vbo, "2f 2f", "in_pos", "in_uv")],
        )
        self.ui_vao = self.ctx.vertex_array(
            self.ui_program,
            [(self.quad_vbo, "2f 2f", "in_pos", "in_uv")],
        )

        self.scene_color = self.ctx.texture((width, height), 4)
        self.scene_depth = self.ctx.depth_texture((width, height))
        self.scene_fbo = self.ctx.framebuffer(self.scene_color, self.scene_depth)
        self.scene_color.filter = (moderngl.LINEAR, moderngl.LINEAR)

        self.ui_texture = self.ctx.texture((width, height), 4)
        self.ui_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)

        self._time_sec = 0.0

    def resize(self, width: int, height: int):
        if width == self.width and height == self.height:
            return
        self.width = max(1, width)
        self.height = max(1, height)
        self.scene_color.release()
        self.scene_depth.release()
        self.scene_fbo.release()
        self.ui_texture.release()

        self.scene_color = self.ctx.texture((self.width, self.height), 4)
        self.scene_depth = self.ctx.depth_texture((self.width, self.height))
        self.scene_fbo = self.ctx.framebuffer(self.scene_color, self.scene_depth)
        self.scene_color.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.ui_texture = self.ctx.texture((self.width, self.height), 4)
        self.ui_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.ctx.viewport = (0, 0, self.width, self.height)

    def _camera(self, game: QuizGameState) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        shake = game.camera_shake
        wobble_x = math.sin(self._time_sec * 27.0) * 0.06 * shake
        wobble_y = math.cos(self._time_sec * 21.0) * 0.05 * shake
        eye = np.array([wobble_x, 6.3 + wobble_y, -19.0], dtype=np.float32)
        center = np.array([0.0, 0.0, game.tuning.hit_z + 12.0], dtype=np.float32)
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        view = look_at(eye, center, up)
        proj = perspective(44.0, self.width / max(1.0, float(self.height)), 0.1, 160.0)
        return eye, view, proj

    def _draw_cube(
        self,
        view: np.ndarray,
        proj: np.ndarray,
        position: tuple[float, float, float],
        scaling: tuple[float, float, float],
        color: tuple[float, float, float],
        eye: np.ndarray,
        emissive: float = 0.0,
    ):
        model = mat4_mul(translate(position), scale(scaling))
        mvp = mat4_mul(proj, mat4_mul(view, model))
        self.scene_program["u_model"].write(model.T.tobytes())
        self.scene_program["u_mvp"].write(mvp.T.tobytes())
        self.scene_program["u_color"].value = color
        self.scene_program["u_camera_pos"].value = tuple(float(x) for x in eye)
        self.scene_program["u_dir_light_dir"].value = (-0.3, -1.0, -0.4)
        self.scene_program["u_dir_light_color"].value = (0.9, 0.95, 1.0)
        self.scene_program["u_point_light_pos"].value = (0.0, 1.8, -6.0)
        self.scene_program["u_point_light_color"].value = (0.45, 0.52, 0.95)
        self.scene_program["u_emissive"].value = float(emissive)
        self.cube_vao.render()

    def _draw_world(self, game: QuizGameState):
        eye, view, proj = self._camera(game)
        t = game.tuning

        # Corridor shell.
        self._draw_cube(view, proj, (0, -1.3, 8), (12, 0.1, 64), (0.16, 0.19, 0.30), eye)
        self._draw_cube(view, proj, (-6, 1.2, 8), (0.2, 5, 64), (0.09, 0.11, 0.18), eye)
        self._draw_cube(view, proj, (6, 1.2, 8), (0.2, 5, 64), (0.09, 0.11, 0.18), eye)
        self._draw_cube(view, proj, (0, 3.7, 8), (12, 0.2, 64), (0.07, 0.08, 0.14), eye)

        for z in range(-6, 53, 4):
            self._draw_cube(view, proj, (0, -1.23, float(z)), (0.03, 0.03, 2.2), (0.7, 0.73, 0.92), eye)

        # Player.
        p_glow = 0.18 + game.correct_flash * 0.26
        self._draw_cube(
            view,
            proj,
            (game.player_x, -0.65, t.hit_z),
            (1.2, 1.3, 1.2),
            (0.27, 0.72, 0.95),
            eye,
            emissive=p_glow,
        )

        if game.game_state == STATE_MENU:
            return

        wall_z = game.wall_z
        # Wall slabs with two holes.
        self._draw_cube(view, proj, (0, 0.45, wall_z), (11.6, 3.6, 0.55), (0.56, 0.58, 0.71), eye)
        self._draw_cube(view, proj, (t.left_door_x, 0.18, wall_z), (2.7, 2.5, 0.60), (0.05, 0.06, 0.12), eye)
        self._draw_cube(view, proj, (t.right_door_x, 0.18, wall_z), (2.7, 2.5, 0.60), (0.05, 0.06, 0.12), eye)

        # Door frames (emissive accents).
        glow = 0.16 + game.correct_flash * 0.9 + game.wrong_flash * 0.8
        self._draw_cube(
            view,
            proj,
            (t.left_door_x, 0.18, wall_z - 0.33),
            (2.84, 2.64, 0.16),
            (0.86, 0.31, 0.29),
            eye,
            emissive=glow,
        )
        self._draw_cube(
            view,
            proj,
            (t.right_door_x, 0.18, wall_z - 0.33),
            (2.84, 2.64, 0.16),
            (0.33, 0.53, 0.95),
            eye,
            emissive=glow * 0.8,
        )

    def _upload_ui(self, ui_surface: pygame.Surface):
        if ui_surface.get_width() != self.width or ui_surface.get_height() != self.height:
            ui_surface = pygame.transform.smoothscale(ui_surface, (self.width, self.height))
        ui_bytes = pygame.image.tobytes(ui_surface, "RGBA", True)
        self.ui_texture.write(ui_bytes)

    def render(self, game: QuizGameState, ui_surface: pygame.Surface, dt: float):
        self._time_sec += dt
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.scene_fbo.use()
        if game.game_state == STATE_MENU:
            self.ctx.clear(0.96, 0.94, 0.91, 1.0)
        else:
            # Keep a deep blue base for gameplay.
            self.ctx.clear(0.05, 0.06, 0.11, 1.0)
        self._draw_world(game)

        # Post process to default framebuffer.
        self.ctx.screen.use()
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.scene_color.use(location=0)
        self.post_program["u_scene"].value = 0
        self.post_program["u_time"].value = self._time_sec
        if game.wrong_flash > game.correct_flash:
            hit_flash = 0.6 + min(0.4, game.wrong_flash)
        else:
            hit_flash = min(0.5, game.correct_flash)
        self.post_program["u_hit_flash"].value = hit_flash
        self.post_vao.render()

        # UI overlay.
        self._upload_ui(ui_surface)
        self.ui_texture.use(location=1)
        self.ui_program["u_ui"].value = 1
        self.ui_vao.render()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
