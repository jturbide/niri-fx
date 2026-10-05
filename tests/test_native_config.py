"""Include snapshots preserve file boundaries and freeze every referenced byte."""

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from niri_fx import native_config, setup


class NativeConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native config tests ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "config.kdl"

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def snapshot(self, text=None):
        if text is not None:
            self.config.write_text(text)
        return native_config.snapshot(self.config)

    def test_file_boundaries_order_repeated_includes_and_original_bytes_survive(self):
        self.write("parts/look.kdl", 'animations { slowdown 0.8; }\ninclude "../shared.kdl"\n')
        self.write("shared.kdl", "prefer-no-csd\n")
        source = (
            '// Before\ninclude "parts/look.kdl"\nlayout {}\ninclude "parts/look.kdl" // Again\n'
        )
        self.config.write_text(source)
        before = {path: path.read_bytes() for path in self.root.rglob("*.kdl")}
        result = self.snapshot()
        self.assertEqual(
            result["files"]["config.kdl"],
            source.replace('"parts/look.kdl"', '"config/0001.kdl"').encode(),
        )
        self.assertEqual(
            result["files"]["config/0001.kdl"],
            b'animations { slowdown 0.8; }\ninclude "0002.kdl"\n',
        )
        self.assertEqual(result["files"]["config/0002.kdl"], b"prefer-no-csd\n")
        self.assertEqual(len(result["observed"]), 3)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(set(self.root.rglob("*.kdl")), set(before))
        self.assertEqual(
            native_config.inspect_snapshot(result["root"], result["files"]), result["fingerprint"]
        )

    def test_comments_raw_paths_quoted_names_and_continuations_keep_other_spans(self):
        self.write("a b.kdl", "prefer-no-csd\n")
        source = '/* outer /* nested */ comment */\r\n"include" \\\r\n  r##"a b.kdl"## optional=false; // trailing\r\n'
        result = self.snapshot(source)
        expected = source.replace('r##"a b.kdl"##', '"config/0001.kdl"')
        self.assertEqual(result["files"]["config.kdl"], expected.encode())
        self.assertEqual(len(result["files"]), 2)

    def test_opaque_shader_strings_and_inactive_include_nodes_are_not_followed(self):
        source = """// include "absent.kdl"
/* include "other.kdl" */
/- include "ignored.kdl"
/- (custom)include "typed-ignored.kdl"
animations {
    window-open { custom-shader r#"void main() { // include "shader.kdl" }"#; }
}
/- fake-node { include "child.kdl"; }
"""
        result = self.snapshot(source)
        self.assertEqual(result["files"], {"config.kdl": source.encode()})
        self.assertEqual(len(result["observed"]), 1)

    def test_slash_dash_arguments_and_properties_do_not_change_active_path(self):
        self.write("chosen.kdl", "prefer-no-csd\n")
        text = 'include /- "ignored.kdl" /- optional=false "chosen.kdl" optional=true\n'
        result = self.snapshot(text)
        self.assertEqual(
            result["files"]["config.kdl"],
            text.replace('"chosen.kdl"', '"config/0001.kdl"').encode(),
        )
        self.assertEqual(result["missing_optional"], [])

    def test_optional_absence_is_frozen_and_observed_for_later_conflicts(self):
        result = self.snapshot('include "missing.kdl" optional=true\n')
        self.assertEqual(result["missing_optional"], [str(self.root / "missing.kdl")])
        frozen = result["files"]["config/0001.kdl"]
        self.assertIn(b"Optional include was absent", frozen)
        self.assertNotIn(str(self.root).encode(), frozen)
        observed = next(item for item in result["observed"] if item["before"] is None)
        self.assertNotIn("expected_mode", observed)
        setup.check_unchanged(observed, None)
        self.write("missing.kdl", "prefer-no-csd\n")
        with self.assertRaisesRegex(ValueError, "File changed"):
            setup.check_unchanged(observed, None)
        later = self.snapshot()
        self.assertNotEqual(result["fingerprint"], later["fingerprint"])
        self.assertEqual(result["files"]["config/0001.kdl"], frozen)

    def test_missing_required_file_and_missing_optional_then_required_refuse(self):
        for source in (
            'include "absent.kdl"\n',
            'include "absent.kdl" optional=false\n',
            'include "absent.kdl" optional=true\ninclude "absent.kdl"\n',
        ):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "Required config include is missing"):
                    self.snapshot(source)

    def test_absolute_and_home_includes_become_owned_relative_paths(self):
        external = self.write("outside/absolute.kdl", "prefer-no-csd\n")
        self.write("home/user.kdl", "layout {}\n")
        self.config.write_text(f'include "{external}"\ninclude "~/user.kdl"\n')
        with patch.object(Path, "home", return_value=self.root / "home"):
            result = self.snapshot()
        self.assertEqual(
            result["files"]["config.kdl"], b'include "config/0001.kdl"\ninclude "config/0002.kdl"\n'
        )
        self.assertNotIn(str(self.root).encode(), b"".join(result["files"].values()))

    def test_unicode_escaped_include_names_and_paths_are_understood(self):
        self.write("é.kdl", "prefer-no-csd\n")
        result = self.snapshot('"\\u{69}nclude" "\\u{e9}.kdl"\n')
        self.assertEqual(result["files"]["config.kdl"], b'"\\u{69}nclude" "config/0001.kdl"\n')

    def test_bom_prefixed_includes_are_snapshotted_and_never_treated_as_self_contained(self):
        self.write("child.kdl", "prefer-no-csd\n")
        for name in ("include", '"include"'):
            for prefix in ("\ufeff", "\ufeff\ufeff", " \ufeff", "// comment\n\ufeff"):
                source = f'{prefix}{name}\ufeff "child.kdl"\n'
                result = self.snapshot(source)
                self.assertEqual(len(result["files"]), 2)
                self.assertIn(b"\xef\xbb\xbf", result["files"]["config.kdl"])
                with self.assertRaisesRegex(ValueError, "no active include"):
                    native_config.require_self_contained(source.encode())
        native_config.require_self_contained(b'\xef\xbb\xbf// include "inactive.kdl"\n')

    def test_ambiguous_include_forms_and_annotations_are_refused(self):
        cases = [
            '(custom)include "absent.kdl"\n',
            '("custom type")"include" "absent.kdl"\n',
            'include (string)"absent.kdl"\n',
            "include absent.kdl\n",
            'include "a.kdl" "b.kdl"\n',
            'include "a.kdl" optional="true"\n',
            'include "a.kdl" optional=true optional=false\n',
            'include "a.kdl" unknown=true\n',
            'include "a.kdl" { prefer-no-csd; }\n',
            'animations { include "a.kdl"; }\n',
            'include "*.kdl"\n',
            'include "a[1].kdl"\n',
        ]
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    self.snapshot(source)

    def test_unterminated_or_ambiguous_syntax_does_not_hide_includes(self):
        for source in (
            "/* unclosed",
            'include "unclosed',
            'include r#"unclosed',
            "animations {\n",
            "}\n",
            'include \\ "a.kdl"\n',
            'node {} include "a.kdl"\n',
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    self.snapshot(source)

    def test_deep_node_nesting_is_rejected_before_python_recursion_limit(self):
        with self.assertRaisesRegex(ValueError, "node nesting"):
            self.snapshot("node {\n" * 1500 + "}\n" * 1500)

    def test_parent_traversal_cannot_turn_missing_or_nondirectory_paths_into_existing_files(self):
        self.write("present.kdl", "prefer-no-csd\n")
        self.write("regular-file", "contents\n")
        (self.root / "directory").mkdir()
        for prefix in ("missing", "regular-file", "directory/../regular-file"):
            for optional in ("", " optional=true"):
                with self.subTest(prefix=prefix, optional=optional):
                    with self.assertRaisesRegex(ValueError, "parent traversal"):
                        self.snapshot(f'include "{prefix}/../present.kdl"{optional}\n')
        result = self.snapshot('include "directory/../present.kdl"\n')
        self.assertEqual(result["files"]["config/0001.kdl"], b"prefer-no-csd\n")

    def test_trailing_directory_components_cannot_turn_failed_file_reads_into_includes(self):
        self.write("present.kdl", "prefer-no-csd\n")
        for path in ("present.kdl/", "present.kdl/.", "present.kdl/.."):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "end in a filename"):
                    self.snapshot(f'include "{path}"\n')

    def test_cyclic_includes_and_alias_cycles_are_rejected(self):
        self.write("a.kdl", 'include "b.kdl"\n')
        self.write("b.kdl", 'include "./a.kdl"\n')
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.snapshot('include "a.kdl"\n')
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.snapshot('include "./config.kdl"\n')

    def test_symlink_sources_ancestors_and_optional_symlinks_are_rejected(self):
        target = self.write("real/child.kdl", "prefer-no-csd\n")
        (self.root / "link.kdl").symlink_to(target)
        (self.root / "linked-directory").symlink_to(target.parent, target_is_directory=True)
        (self.root / "dangling.kdl").symlink_to(self.root / "missing.kdl")
        for source in (
            'include "link.kdl"\n',
            'include "linked-directory/child.kdl"\n',
            'include "dangling.kdl" optional=true\n',
            'include "linked-directory/../config.kdl"\n',
        ):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "symlinks"):
                    self.snapshot(source)

    def test_special_files_are_rejected_without_reading_or_freezing_them(self):
        os.mkfifo(self.root / "pipe.kdl")
        for suffix in ("", " optional=true"):
            with self.assertRaisesRegex(ValueError, "regular file"):
                self.snapshot(f'include "pipe.kdl"{suffix}\n')
        self.write("directory/keep", "value")
        with self.assertRaises((ValueError, OSError)):
            self.snapshot('include "directory" optional=true\n')

    def test_source_observations_detect_user_edits_modes_and_fifo_replacement(self):
        child = self.write("child.kdl", "prefer-no-csd\n")
        result = self.snapshot('include "child.kdl"\n')
        observation = next(item for item in result["observed"] if item["logical"] == str(child))
        child.write_text("layout {}\n")
        with self.assertRaisesRegex(ValueError, "File changed"):
            setup.check_unchanged(observation, observation["before"])
        child.write_bytes(observation["before"])
        child.chmod(0o700)
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            setup.check_unchanged(observation, observation["before"])
        child.unlink()
        os.mkfifo(child)
        with self.assertRaisesRegex(ValueError, "regular file"):
            setup.check_unchanged(observation, observation["before"])

    def test_file_byte_count_include_count_and_depth_are_bounded(self):
        self.write("child.kdl", "prefer-no-csd\n")
        self.config.write_text('include "child.kdl"\n')
        for setting, limit, fragment in (
            ("MAX_FILES", 1, "Too many files"),
            ("MAX_FILE_BYTES", 4, "file exceeds"),
            ("MAX_TOTAL_BYTES", 20, "total size"),
            ("MAX_INCLUDE_NODES", 0, "include nodes"),
            ("MAX_DEPTH", 0, "depth limit"),
        ):
            with self.subTest(setting=setting), patch.object(native_config, setting, limit):
                with self.assertRaisesRegex(ValueError, fragment):
                    self.snapshot()

    def test_snapshot_inspection_rejects_external_missing_unreachable_and_cyclic_files(self):
        for files in (
            {"config.kdl": b'include "/external.kdl"\n'},
            {"config.kdl": b'include "../outside.kdl"\n'},
            {"config.kdl": b'include "missing.kdl" optional=true\n'},
            {"config.kdl": b"", "config/0001.kdl": b"unreachable\n"},
            {"config.kdl": b'include "config.kdl"\n'},
            {"config.kdl": b"", "../foreign.kdl": b""},
        ):
            with self.subTest(files=files):
                with self.assertRaises(ValueError):
                    native_config.inspect_snapshot("config.kdl", files)

    def test_longest_shared_include_path_is_checked_even_after_shorter_visit(self):
        files = {
            "config.kdl": b'include "config/0001.kdl"\ninclude "config/0002.kdl"\n',
            "config/0001.kdl": b'include "0003.kdl"\n',
            "config/0002.kdl": b'include "0001.kdl"\n',
            "config/0003.kdl": b"",
        }
        with patch.object(native_config, "MAX_DEPTH", 2):
            with self.assertRaisesRegex(ValueError, "depth limit"):
                native_config.inspect_snapshot("config.kdl", files)

    def test_identity_is_location_independent_but_tracks_every_included_byte(self):
        self.write("child.kdl", "prefer-no-csd\n")
        first = self.snapshot('include "child.kdl"\n')
        self.write("elsewhere/child.kdl", "prefer-no-csd\n")
        elsewhere = self.write("elsewhere/config.kdl", 'include "child.kdl"\n')
        self.assertEqual(first["fingerprint"], native_config.snapshot(elsewhere)["fingerprint"])
        changed = copy.deepcopy(first["files"])
        changed["config/0001.kdl"] += b"// edit\n"
        self.assertNotEqual(
            first["fingerprint"], native_config.inspect_snapshot("config.kdl", changed)
        )


if __name__ == "__main__":
    unittest.main()
