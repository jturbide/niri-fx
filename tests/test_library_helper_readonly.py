"""Reading an installed shell helper must not dirty its source checkout."""

import json
import os
import py_compile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import shell_registry

from niri_fx.documents import effect_document
from niri_fx.library import Library
from niri_fx.presets import PRESETS


def tree_snapshot(root):
    """Include directory entries, bytes, permissions and modification times."""
    result = {}
    for path in (root, *sorted(root.rglob("*"))):
        stat = path.stat()
        result[str(path.relative_to(root))] = (
            stat.st_mode,
            stat.st_mtime_ns,
            None if path.is_dir() else path.read_bytes(),
        )
    return result


class LibraryHelperReadonlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.shell = self.root / "shell"
        scripts = self.shell / "scripts"
        scripts.mkdir(parents=True)
        (self.shell / "README.md").write_text("Synthetic upstream shell checkout\n")
        (self.shell / "settings.qml").write_text("// Keep unrelated shell settings\n")
        self.helper = scripts / "niri-config.py"
        registry = shell_registry()
        registry["presets"][0]["name"] = "Native settings"
        self.helper.write_text(
            "import json\nimport os\nimport sys\nfrom pathlib import Path\n"
            'VERSION = "old"\n'
            f"SHELL = {registry!r}\n"
            "def _load_animation_presets(): return SHELL\n"
            "def resolve_niri_section_file(path):\n"
            "    return Path(os.environ['XDG_CONFIG_HOME']) / 'niri' / path\n"
            "def _write_validated(path, text):\n"
            "    raise AssertionError('Review must capture the serializer output')\n"
            "def cmd_apply_animation_preset(ids):\n"
            "    preset = _load_animation_presets()['presets'][0]\n"
            "    assert ids == [preset['id']]\n"
            "    assert __name__ == '_nirifx_inir_helper'\n"
            "    text = '// ' + VERSION + ' via ' + Path(__file__).name + '\\n'\n"
            "    text += '// ' + json.dumps(preset['types'], sort_keys=True) + '\\n'\n"
            "    text += 'animations { slowdown 1.5; }\\n'\n"
            "    return _write_validated(resolve_niri_section_file('config.d/60-animations.kdl'), text)\n"
            "if __name__ == '__main__':\n"
            "    assert sys.argv[1:] == ['get-animation-presets']\n"
            "    print(json.dumps(_load_animation_presets()))\n"
        )
        config_root = self.root / "config"
        self.config = config_root / "niri/config.kdl"
        self.animation = self.config.parent / "config.d/60-animations.kdl"
        self.animation.parent.mkdir(parents=True)
        self.config.write_text('include "config.d/60-animations.kdl"\n')
        self.animation.write_text("// Preserve these bytes\nanimations { slowdown 1.5; }\n")
        self.registry = config_root / "inir/niri-animation-presets.json"
        self.registry.parent.mkdir()
        self.registry.write_text('{"presets":[]}\n')
        self.library = Library(
            SimpleNamespace(
                config=self.config,
                state=self.root / "state",
                registry=self.registry,
                inir_root=self.shell,
                base="auto",
            ),
            "inir",
        )
        self.selection = {
            "document": effect_document("Demo", PRESETS["balanced"]),
            "allow_resize": False,
            "allow_movement": False,
        }
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_root)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def assert_readonly_review(self, version):
        before = tree_snapshot(self.root)
        # Catch the regression even when the test runner was launched with -B.
        with patch("sys.dont_write_bytecode", False):
            listing = self.library.listing()
            review = self.library.review(self.selection)
            plan = self.library.plan(self.selection)
        self.assertEqual(tree_snapshot(self.root), before)
        self.assertEqual(listing["active_name"], "Native settings")
        self.assertEqual(review["target"], "inir-active")
        self.assertEqual(len(review["changes"]), 2)
        animation = next(
            item["after"] for item in plan["changes"] if item["logical"] == str(self.animation)
        )
        self.assertTrue(animation.startswith(f"// {version} via niri-config.py\n".encode()))
        self.assertIn(b'"window-open"', animation)
        self.assertIn(b'"custom-shader"', animation)
        self.assertIn(b'"workspace-switch": {"spring": [0.9, 700, 0.0001]}', animation)
        self.assertIn(b"slowdown 1.5", animation)
        registry = next(
            item["after"] for item in plan["changes"] if item["logical"] == str(self.registry)
        )
        self.assertEqual(json.loads(registry)["presets"][0]["id"], "niri-fx-custom-demo")

    def test_listing_and_review_leave_the_entire_shell_and_config_trees_unchanged(self):
        self.assert_readonly_review("old")

    def test_review_uses_current_source_without_reading_or_replacing_an_existing_cache(self):
        py_compile.compile(str(self.helper), doraise=True)
        before = self.helper.stat()
        self.helper.write_text(
            self.helper.read_text().replace('VERSION = "old"', 'VERSION = "new"')
        )
        # The stale cache still passes the loader's timestamp/size check.
        os.utime(self.helper, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assert_readonly_review("new")


if __name__ == "__main__":
    unittest.main()
