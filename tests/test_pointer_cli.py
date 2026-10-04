"""Portable CLI composition stays independent of experimental activation."""

import io
import json
import unittest
from contextlib import redirect_stdout
from dataclasses import asdict
from pathlib import Path

from niri_fx.cli import main, parser
from niri_fx.documents import parse_document
from niri_fx.pointer import PRESETS


class PointerCliTests(unittest.TestCase):
    def document(self, *options):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["profile", *options]), 0)
        document = json.loads(output.getvalue())
        parse_document(document)
        return document

    def test_pointer_preset_can_be_composed_with_actions_or_a_set_without_activation(self):
        plain = self.document()
        self.assertNotIn("pointer", plain)
        for name, preset in PRESETS.items():
            document = self.document("--pointer", name, "--open-preset", "zipper")
            self.assertEqual(document["pointer"], asdict(preset.wobble))
            self.assertIsNone(document["actions"]["movement"])
        disabled = self.document("--action-set", "fragments-motion", "--pointer", "off")
        self.assertEqual(disabled["pointer"]["strength"], 0)

    def test_shared_binary_alias_selects_the_same_compositor_for_all_local_interfaces(self):
        for command in ("studio", "doctor", "setup"):
            for option in ("--niri-binary", "--movement-binary"):
                args = parser().parse_args([command, option, "/trusted/niri"])
                self.assertEqual(args.movement_binary, Path("/trusted/niri"))
        args = parser().parse_args(["setup", "--enable-pointer"])
        self.assertTrue(args.enable_pointer)
        self.assertFalse(args.apply)


if __name__ == "__main__":
    unittest.main()
