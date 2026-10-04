"""Shape document contracts and a forward-motion check of inverse lookup bounds."""

import math
import random
import unittest
from dataclasses import replace

from niri_fx.cli import parser, selected_effect
from niri_fx.documents import effect_document, parse_document
from niri_fx.effects import (
    PRESETS,
    animation_types,
    movement_shader,
    renderer_name,
    shape_search_radius,
)
from niri_fx.model import FRAGMENT_SHAPES, Effect


class FragmentShapeTests(unittest.TestCase):
    def test_shape_mixtures_round_trip_and_keep_single_shape_endpoints(self):
        for first in FRAGMENT_SHAPES:
            for second in FRAGMENT_SHAPES:
                with self.subTest(first=first, second=second):
                    effect = replace(
                        Effect(),
                        fragment_shape=first,
                        fragment_secondary=second,
                        fragment_mix=0.45,
                        fragment_shape_seed=4021,
                    )
                    self.assertEqual(parse_document(effect_document("Mixed", effect))[2], effect)
                    self.assertEqual(effect.mixed_shapes, first != second)
                    self.assertEqual(
                        shape_search_radius(replace(effect, fragment_mix=1)),
                        shape_search_radius(replace(effect, fragment_shape=second, fragment_mix=0)),
                    )
                    self.assertEqual(
                        renderer_name(replace(effect, fragment_mix=0)),
                        renderer_name(replace(effect, fragment_secondary="circle", fragment_mix=0)),
                    )
        self.assertTrue(all(not style.resize for style in PRESETS.values()))

    def test_shapes_round_trip_through_cli_and_documents_without_resize(self):
        for shape in FRAGMENT_SHAPES:
            with self.subTest(shape=shape):
                effect = selected_effect(
                    parser().parse_args(
                        [
                            "render",
                            "--fragment-shape",
                            shape,
                            "--fragment-aspect",
                            "2.4",
                            "--fragment-orientation",
                            "-35",
                            "--fragment-transition",
                            "0.4",
                        ]
                    )
                )
                self.assertEqual(effect.fragment_shape, shape)
                self.assertEqual(effect.fragment_aspect, 2.4)
                self.assertEqual(effect.fragment_orientation, -35)
                self.assertEqual(effect.fragment_transition, 0.4)
                self.assertEqual(parse_document(effect_document("Shape", effect))[2], effect)
                self.assertNotIn("window-resize", animation_types(effect))
                self.assertNotIn("window-movement", animation_types(effect))
                self.assertIn("vec4 move_color", movement_shader(effect))

    def test_existing_square_styles_keep_their_renderer(self):
        self.assertEqual(renderer_name(PRESETS["balanced"]), "gravity")
        self.assertEqual(renderer_name(PRESETS["mosaic-burst"]), "varied")
        self.assertEqual(renderer_name(replace(Effect(), fragment_orientation=10)), "shaped")
        # Stored but irrelevant aspect ratios do not change square rendering.
        self.assertEqual(renderer_name(replace(Effect(), fragment_aspect=4)), "gravity")
        self.assertEqual(
            renderer_name(replace(Effect(), fragment_roundness=1, fragment_transition=0.5)),
            "shaped",
        )
        self.assertTrue(all(not effect.resize for effect in PRESETS.values()))

    def test_lookup_bound_covers_forward_transformed_piece_extremes(self):
        """Search around the inverse estimate must include the actual source cell.

        Sample forward points, not the shader's inverse loop. Piece radius and
        local motion are normalized by field scale, covering inward fields too.
        The inverse wave is tested at its maximum derivative in both directions.
        """
        rng = random.Random(719)

        def turn(point, angle):
            c, s = math.cos(angle), math.sin(angle)
            return (c * point[0] - s * point[1], s * point[0] + c * point[1])

        for shape in FRAGMENT_SHAPES:
            for aspect in (0.25, 1, 4):
                for wave, resizing in ((0, False), (1, False), (0, True)):
                    effect = replace(
                        Effect(),
                        fragment_shape=shape,
                        fragment_aspect=aspect,
                        wave_strength=wave,
                        dispersion=1,
                    )
                    bound = shape_search_radius(effect, resizing=resizing)
                    used_aspect = 1 if shape in {"square", "circle"} else aspect
                    stretch = (math.sqrt(used_aspect), 1 / math.sqrt(used_aspect))
                    for _ in range(160):
                        cell = (rng.randrange(-30, 30), rng.randrange(-30, 30))
                        part = rng.randrange(2)
                        if shape == "hexagon":
                            center = (math.sqrt(3) * (cell[0] + cell[1] * 0.5), 1.5 * cell[1])
                            vertex_angle = math.pi / 6 + rng.randrange(6) * math.pi / 3
                            vertex = (math.cos(vertex_angle), math.sin(vertex_angle))
                        elif shape == "triangle":
                            offset = 1 / 3 if part == 0 else 2 / 3
                            center = (cell[0] + offset, cell[1] + offset)
                            vertex = rng.choice(
                                ((0, 0), (1, 0), (0, 1)) if part == 0 else ((1, 1), (1, 0), (0, 1))
                            )
                            vertex = (vertex[0] - offset, vertex[1] - offset)
                        else:
                            center = (cell[0] + 0.5, cell[1] + 0.5)
                            vertex = (rng.choice((-0.5, 0.5)), rng.choice((-0.5, 0.5)))
                        orientation, spin, wander = (
                            rng.uniform(-math.pi, math.pi) for _ in range(3)
                        )
                        edge = turn(
                            (vertex[0] * stretch[0], vertex[1] * stretch[1]), orientation + spin
                        )
                        reach = 0.4 if resizing else 0.72
                        delta = (
                            edge[0] + reach * math.cos(wander),
                            edge[1] + reach * math.sin(wander),
                        )
                        # Undo the maximum horizontal wave slope at the displaced Y.
                        delta = (delta[0] + rng.choice((-0.45, 0.45)) * wave * delta[1], delta[1])
                        delta = turn(delta, -orientation)
                        point = (
                            center[0] + delta[0] / stretch[0],
                            center[1] + delta[1] / stretch[1],
                        )
                        if shape == "hexagon":
                            point = (point[0] / math.sqrt(3) - point[1] / 3, point[1] * 2 / 3)
                        offsets = (cell[0] - math.floor(point[0]), cell[1] - math.floor(point[1]))
                        self.assertLessEqual(
                            max(map(abs, offsets)), bound, (shape, aspect, wave, resizing, offsets)
                        )
