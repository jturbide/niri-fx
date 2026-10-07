"""Reading an installed shell helper must not dirty its source checkout."""

import json
import os
import py_compile
import tempfile
import unittest
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from helpers import shell_registry

from niri_fx.documents import effect_document
from niri_fx.inir_serializer import serialize_preset
from niri_fx.library import Library
from niri_fx.presets import PRESETS
from niri_fx.storage import digest
from niri_fx.studio import make_server


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

    def test_review_fingerprint_uses_the_exact_executed_source_snapshot(self):
        original = self.helper.read_bytes()
        read_bytes = Path.read_bytes
        reads = []

        def read(path):
            if path == self.helper:
                reads.append(path)
                return original if len(reads) == 1 else original + b"# Replaced source\n"
            return read_bytes(path)

        with patch.object(Path, "read_bytes", read):
            plan = self.library.plan(self.selection)
        self.assertEqual(len(reads), 1)
        self.assertEqual(plan["selection"]["helper_sha256"], digest(original))

    def test_contract_drift_is_actionable_and_leaves_all_files_unchanged(self):
        original = self.helper.read_text()
        replacements = {
            "missing resolver": "del resolve_niri_section_file",
            "non-callable serializer": "cmd_apply_animation_preset = None",
            "changed serializer arguments": "def cmd_apply_animation_preset(ids, required): pass",
            "changed writer arguments": "def _write_validated(path, text, required): pass",
            "missing loader": "del _load_animation_presets",
            "invalid resolved path": "def resolve_niri_section_file(path): return None",
            "relative resolved path": "def resolve_niri_section_file(path): return Path(path)",
            "unexpected resolved path": "def resolve_niri_section_file(path): return Path('/tmp/unexpected.kdl')",
            "different captured path": (
                "def cmd_apply_animation_preset(ids):\n"
                "    return _write_validated(Path('/tmp/unexpected.kdl'), 'animations {}')"
            ),
            "no output": "def cmd_apply_animation_preset(ids): return 0",
            "failed status": "def cmd_apply_animation_preset(ids): return 1",
            "non-integer status": (
                "old_serializer = cmd_apply_animation_preset\n"
                "def cmd_apply_animation_preset(ids):\n"
                "    old_serializer(ids)\n"
                "    return False"
            ),
            "multiple outputs": (
                "old_serializer = cmd_apply_animation_preset\n"
                "def cmd_apply_animation_preset(ids):\n"
                "    old_serializer(ids)\n"
                "    return old_serializer(ids)"
            ),
            "empty output": (
                "def cmd_apply_animation_preset(ids):\n"
                "    return _write_validated(resolve_niri_section_file('config.d/60-animations.kdl'), '')"
            ),
            "non-text output": (
                "def cmd_apply_animation_preset(ids):\n"
                "    return _write_validated(resolve_niri_section_file('config.d/60-animations.kdl'), b'animations {}')"
            ),
            "helper failure": (
                "def cmd_apply_animation_preset(ids): raise RuntimeError('Changed helper contract')"
            ),
        }
        for label, replacement in replacements.items():
            with self.subTest(label=label):
                self.helper.write_text(original + "\n" + replacement + "\n")
                before = tree_snapshot(self.root)
                with self.assertRaisesRegex(
                    ValueError, "iNiR's animation helper is incompatible.*--target standalone"
                ):
                    self.library.review(self.selection)
                self.assertEqual(tree_snapshot(self.root), before)

    def test_changed_source_after_review_refuses_before_creating_a_transaction(self):
        review = self.library.review(self.selection)
        # A code-only change still invalidates review even with identical output.
        self.helper.write_bytes(self.helper.read_bytes() + b"\n# Compatible upstream update\n")
        before = tree_snapshot(self.root)
        with self.assertRaisesRegex(ValueError, "setup plan changed"):
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        self.assertEqual(tree_snapshot(self.root), before)

    def test_monolithic_config_and_existing_section_symlink_remain_supported(self):
        original = self.helper.read_text()
        external = self.root / "dotfiles/animations.kdl"
        external.parent.mkdir()
        self.animation.rename(external)
        self.animation.symlink_to(external)
        self.assert_readonly_review("old")
        self.helper.write_text(
            original + f"\ndef resolve_niri_section_file(path): return Path({str(self.config)!r})\n"
        )
        before_config = self.config.read_bytes()
        before_shell = tree_snapshot(self.shell)
        with patch("niri_fx.setup.validate_config"):
            review = self.library.review(self.selection)
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        self.assertTrue(self.config.read_bytes().startswith(b"// old via niri-config.py"))
        self.library.undo()
        self.assertEqual(self.config.read_bytes(), before_config)
        self.assertEqual(tree_snapshot(self.shell), before_shell)
        self.assertTrue(self.animation.is_symlink())

    def test_relative_expected_config_keeps_supported_absolute_helper_output(self):
        before = tree_snapshot(self.root)
        previous = Path.cwd()
        os.chdir(self.root)
        try:
            result = serialize_preset(
                self.shell, "config/niri/config.kdl", {"id": "native", "types": {}}
            )
        finally:
            os.chdir(previous)
        self.assertEqual(result.path, self.animation)
        self.assertEqual(tree_snapshot(self.root), before)

    def test_config_alias_symlink_keeps_the_normal_shell_section_supported(self):
        alias = self.root / "config-alias.kdl"
        alias.symlink_to(self.config)
        self.library.config = alias
        self.assert_readonly_review("old")

    def test_compatible_upgrade_and_broken_helper_keep_exact_restore_available(self):
        original_animation = self.animation.read_bytes()
        original_registry = self.registry.read_bytes()
        with patch("niri_fx.setup.validate_config"):
            review = self.library.review(self.selection)
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
            first_animation = self.animation.read_bytes()
            first_registry = self.registry.read_bytes()
            self.helper.write_text(
                self.helper.read_text().replace('VERSION = "old"', 'VERSION = "new"')
            )
            before_shell = tree_snapshot(self.shell)
            review = self.library.review(self.selection)
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        self.assertNotEqual(self.animation.read_bytes(), first_animation)
        self.assertEqual(tree_snapshot(self.shell), before_shell)
        self.helper.write_text(self.helper.read_text() + "\ndel cmd_apply_animation_preset\n")
        before_shell = tree_snapshot(self.shell)
        self.library.undo()
        self.assertEqual(self.animation.read_bytes(), first_animation)
        self.assertEqual(self.registry.read_bytes(), first_registry)
        self.library.undo()
        self.assertEqual(self.animation.read_bytes(), original_animation)
        self.assertEqual(self.registry.read_bytes(), original_registry)
        self.assertEqual(tree_snapshot(self.shell), before_shell)

    def test_restore_after_upgrade_preserves_external_animation_edits(self):
        with patch("niri_fx.setup.validate_config"):
            review = self.library.review(self.selection)
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        self.helper.write_text(
            self.helper.read_text().replace('VERSION = "old"', 'VERSION = "new"')
        )
        self.animation.write_bytes(self.animation.read_bytes() + b"// New shell setting\n")
        before = tree_snapshot(self.root)
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.library.undo()
        self.assertEqual(tree_snapshot(self.root), before)

    def test_keyboard_interrupt_is_not_reported_as_helper_incompatibility(self):
        self.helper.write_text(
            self.helper.read_text()
            + "\ndef cmd_apply_animation_preset(ids): raise KeyboardInterrupt()\n"
        )
        before = tree_snapshot(self.root)
        with self.assertRaises(KeyboardInterrupt):
            self.library.review(self.selection)
        self.assertEqual(tree_snapshot(self.root), before)

    def test_changed_helper_contract_returns_a_normal_studio_error_response(self):
        self.helper.write_text(self.helper.read_text() + "\ndel cmd_apply_animation_preset\n")
        args = SimpleNamespace(
            **vars(self.library.arguments), target="inir", port=0, preset="balanced"
        )
        server = make_server(args, PRESETS["balanced"])
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            token = parse_qs(urlsplit(server.session_url).query)["token"][0]
            request = Request(
                server.origin + "/review",
                json.dumps(self.selection).encode(),
                {
                    "Content-Type": "application/json",
                    "Origin": server.origin,
                    "X-NiriFX-Token": token,
                },
                method="POST",
            )
            before = tree_snapshot(self.root)
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            with caught.exception as response:
                self.assertEqual(response.code, 400)
                error = json.load(response)["error"]
            self.assertIn("missing callable cmd_apply_animation_preset", error)
            self.assertIn("--target standalone", error)
            self.assertEqual(tree_snapshot(self.root), before)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
