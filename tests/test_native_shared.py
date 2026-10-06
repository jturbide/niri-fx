"""Shared configuration follows user files without weakening retained recovery."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import test_native_customization

from niri_fx import native_config, native_customization, native_session, native_shared, setup
from niri_fx.documents import effect_document
from niri_fx.fragment_motion import PRESETS
from niri_fx.model import Effect
from niri_fx.profiles import Profile


class NativeSharedTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_customization.NativeCustomizationTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.plain = self.fixture.stage()
        prepared = self.fixture.plan(self.plain, Profile(open=Effect(), close="off"))
        self.fixture.apply(prepared)
        self.base = prepared["selection"]["bundle_id"]
        self.config = self.fixture.fixture.root / "desktop/config.kdl"
        self.config.parent.mkdir()
        self.config.write_text('include "shell.kdl"\ninput {}\n')
        self.shell = self.config.with_name("shell.kdl")
        self.shell.write_text("animations { window-open { duration-ms 913; }; }\n")
        self.stock = self.fixture.fixture.binary
        self.validator = self.fixture.validator
        self.validator.reset_mock()

    def plan(self):
        return native_shared.share_plan(self.root, self.base, self.config, stock_binary=self.stock)

    def apply(self, plan):
        return native_customization.apply_native(
            plan, self.root, expected=setup.plan_fingerprint(plan)
        )

    def report(self, plan):
        return native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])

    def adopt(self):
        plan = self.plan()
        self.apply(plan)
        return self.report(plan)

    def configure(self, report, profile, *, fragment_preset=None):
        return native_customization.configure_plan(
            self.root,
            report["bundle_id"],
            effect_document("Shared", profile),
            fragment_preset=fragment_preset,
        )

    def test_adoption_is_read_only_until_apply_and_validates_both_targets(self):
        before = {
            path: path.read_bytes()
            for path in self.fixture.fixture.root.rglob("*")
            if path.is_file()
        }
        plan = self.plan()
        self.validator.assert_not_called()
        self.assertEqual(
            before,
            {
                path: path.read_bytes()
                for path in self.fixture.fixture.root.rglob("*")
                if path.is_file()
            },
        )
        result = self.apply(plan)
        report = self.report(plan)
        self.assertEqual(result["activation"], "config-written")
        self.assertEqual(result["live"]["status"], "unverified")
        self.assertNotIn("restore", result)
        self.assertNotEqual(report["config"], report["recovery_config"])
        self.assertEqual(native_shared.inspect_settings(report)["status"], "current")
        self.assertEqual(self.shell.read_bytes(), before[self.shell])
        self.assertTrue(self.config.read_text().startswith('include "shell.kdl"\ninput {}\n'))
        self.assertEqual(
            self.validator.call_args_list[0].args,
            (report["config"], native_session.inspect_bundle(self.root, self.base)["binary"]),
        )
        self.assertEqual(self.validator.call_args_list[1].args, (str(self.config), str(self.stock)))
        self.assertNotIn("window-open", Path(report["shared"]["native_include"]).read_text())
        self.assertIn("window-open", Path(report["shared"]["stock_include"]).read_text())

    def test_preserve_removes_generated_style_and_off_stays_explicit(self):
        report = self.adopt()
        plan = self.configure(
            report, Profile(open=None, close="off", resize="off", movement="off", swap="off")
        )
        self.apply(plan)
        latest = self.report(plan)
        stock = Path(latest["shared"]["stock_include"]).read_text()
        native = Path(latest["shared"]["native_include"]).read_text()
        self.assertNotIn("window-open", stock)
        self.assertIn("window-close {\n        off", stock)
        self.assertIn("window-resize {\n        off", stock)
        self.assertNotIn("window-movement", stock)
        self.assertNotIn("window-swap", stock)
        self.assertIn("window-movement {\n        off", native)
        self.assertIn("window-swap {\n        off", native)
        self.assertIn("duration-ms 913", self.shell.read_text())
        self.assertEqual(report["config"], latest["config"])
        self.assertEqual(native_shared.inspect_settings(latest)["status"], "current")

    def test_native_fragments_never_enter_stock_projection(self):
        report = self.adopt()
        plan = self.configure(
            report, Profile(movement=PRESETS["tear"].effect), fragment_preset="tear"
        )
        self.apply(plan)
        latest = self.report(plan)
        self.assertIn("fragment-motion", Path(latest["shared"]["native_include"]).read_text())
        self.assertNotIn("fragment-motion", Path(latest["shared"]["stock_include"]).read_text())
        self.assertEqual(latest["customization"]["fragment_preset"], "tear")

    def test_external_edits_are_separate_from_retained_integrity(self):
        report = self.adopt()
        self.shell.write_text("layout { gaps 19; }\n")
        again = native_session.inspect_bundle(self.root, report["bundle_id"])
        self.assertEqual(report, again)
        state = native_shared.inspect_settings(again)
        self.assertEqual(state["status"], "changed")
        self.assertTrue(state["projections_match"])
        native_shared.preflight(again)
        plan = self.configure(again, Profile(close="off"))
        self.apply(plan)
        self.assertIn("gaps 19", self.shell.read_text())
        self.assertNotIn("gaps 19", Path(report["recovery_config"]).read_text())

    def test_deleted_or_symlinked_source_still_allows_frozen_recovery(self):
        report = self.adopt()
        original = self.config.read_bytes()
        self.config.unlink()
        self.config.symlink_to(self.shell)
        native_session.inspect_bundle(self.root, report["bundle_id"])
        self.assertEqual(native_shared.inspect_settings(report)["status"], "unavailable")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            native_shared.preflight(report)
        plan = native_shared.recovery_plan(self.root, report["bundle_id"])
        self.assertNotIn("shared", plan)
        self.apply(plan)
        recovered = self.report(plan)
        self.assertNotIn("shared", recovered)
        self.assertTrue(self.config.is_symlink())
        self.assertNotEqual(self.config.read_bytes(), original)
        native_config.snapshot(Path(recovered["config"]))

    def test_source_or_executable_changes_invalidate_review(self):
        plan = self.plan()
        self.shell.write_text("layout {}\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.apply(plan)
        self.assertFalse(Path(plan["shared"]["runtime_config"]).exists())
        plan = self.plan()
        self.stock.write_bytes(b"changed trusted validator\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.apply(plan)

    def test_stock_rejection_rolls_back_native_and_stock_files_and_selector(self):
        plan = self.plan()
        before = {path: path.read_bytes() for path in (self.config, self.root / "selection.json")}
        self.validator.side_effect = [None, ValueError("stock parser rejected settings")]
        with self.assertRaisesRegex(ValueError, "stock parser"):
            self.apply(plan)
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        for key in ("runtime_config", "stock_include", "native_include"):
            self.assertFalse(Path(plan["shared"][key]).exists())

    def test_validation_checks_participate_in_review_and_snapshot(self):
        plan = self.plan()
        expected = setup.plan_fingerprint(plan)
        plan["validation_checks"][0]["binary"] += "-different"
        self.assertNotEqual(expected, setup.plan_fingerprint(plan))
        with self.assertRaisesRegex(ValueError, "plan changed"):
            native_shared.apply_shared(plan, self.root, expected=expected)

    def test_apply_requires_explicit_review_and_removed_include_blocks_preflight(self):
        plan = self.plan()
        with self.assertRaisesRegex(ValueError, "fresh review"):
            native_shared.apply_shared(plan, self.root)
        self.apply(plan)
        report = self.report(plan)
        self.config.write_text(setup.without_managed_block(self.config.read_text()))
        self.assertEqual(native_shared.inspect_settings(report)["status"], "unavailable")
        with self.assertRaises(ValueError):
            native_shared.preflight(report)

    def test_hidden_second_stock_include_or_managed_storage_include_is_refused(self):
        stock = self.config.parent / "nirifx/animations.kdl"
        self.shell.write_text(f"include {json.dumps(str(stock))}\n")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            self.plan()
        self.shell.write_text(
            f"include {json.dumps(str(self.root / 'external.kdl'))} optional=true\n"
        )
        with self.assertRaisesRegex(ValueError, "managed native storage"):
            self.plan()

    def test_unowned_or_edited_projections_are_not_overwritten(self):
        report = self.adopt()
        native = Path(report["shared"]["native_include"])
        native.write_text("animations {}\n")
        with self.assertRaisesRegex(ValueError, "native projection changed"):
            self.configure(report, Profile())
        self.assertEqual(native.read_text(), "animations {}\n")

    def test_orphan_projection_owner_is_preserved(self):
        plan = self.plan()
        owner = Path(plan["shared"]["native_include"]).parent / "selection.json"
        owner.parent.mkdir(parents=True)
        owner.write_bytes(b"unrecognized owner\n")
        owner.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "owner record remains"):
            self.plan()
        self.assertEqual(owner.read_bytes(), b"unrecognized owner\n")

    def test_unowned_stock_include_and_ambiguous_block_are_refused(self):
        stock = self.config.parent / "nirifx/animations.kdl"
        stock.parent.mkdir()
        stock.write_text("animations {}\n")
        with self.assertRaisesRegex(ValueError, "unowned"):
            self.plan()
        stock.unlink()
        self.config.write_text('include "nirifx/manual.kdl"\n')
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            self.plan()

    def test_adopts_existing_recognized_standalone_projection(self):
        stock = self.config.parent / "nirifx/animations.kdl"
        stock.parent.mkdir()
        stock.write_text(setup.OWNED + "\nanimations {}\n")
        stock.chmod(0o600)
        block = f"{setup.BEGIN}\ninclude {json.dumps(str(stock))}\n{setup.END}\n"
        with self.config.open("a") as stream:
            stream.write(block)
        self.adopt()
        self.assertEqual(self.config.read_text().count(setup.BEGIN), 1)

    def test_selecting_previous_shared_recipe_restores_both_projections(self):
        original = self.adopt()
        plan = self.configure(original, Profile(open="off", close=None))
        self.apply(plan)
        self.shell.write_text("layout { gaps 21; }\n")
        with patch(
            "niri_fx.native_shared._projections",
            side_effect=AssertionError("Do not regenerate retained shaders"),
        ):
            rollback = native_session.rollback_plan(self.root)
        self.assertEqual(rollback["shared"]["document"], original["shared"]["document"])
        self.apply(rollback)
        restored = self.report(rollback)
        self.assertEqual(native_shared.inspect_settings(restored)["status"], "current")
        self.assertIn("gaps 21", self.shell.read_text())

    def test_runtime_paths_are_bound_to_binary_identity(self):
        source = self.config
        first = native_shared._paths(self.root, source, "1" * 64)
        second = native_shared._paths(self.root, source, "2" * 64)
        self.assertNotEqual(first["native_include"], second["native_include"])
        self.assertNotEqual(first["runtime_config"], second["runtime_config"])
        self.assertEqual(first["stock_include"], second["stock_include"])

    def test_retained_projection_tampering_fails_inspection(self):
        report = self.adopt()
        asset = Path(report["recovery_config"]).parent / native_shared.FILES["native"]
        asset.write_bytes(b"changed\n")
        with self.assertRaisesRegex(ValueError, "contents changed"):
            native_session.inspect_bundle(self.root, report["bundle_id"])

    def test_source_inside_managed_storage_and_unrecognized_recipe_are_refused(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            native_shared.share_plan(
                self.root, self.base, self.root / "config.kdl", stock_binary=self.stock
            )
        with self.assertRaisesRegex(ValueError, "save a NiriFX recipe"):
            native_shared.share_plan(self.root, self.plain, self.config, stock_binary=self.stock)

    def test_planned_snapshot_observes_original_bytes_and_missing_outputs(self):
        planned = self.config.read_bytes() + b'include "new.kdl"\n'
        child = self.config.with_name("new.kdl")
        snapshot = native_config.snapshot(
            self.config, overrides={self.config: planned, child: b"layout {}\n"}
        )
        originals = {item["logical"]: item["before"] for item in snapshot["observed"]}
        self.assertEqual(originals[str(self.config)], self.config.read_bytes())
        self.assertIsNone(originals[str(child)])
        self.assertFalse(child.exists())
        native_config.inspect_snapshot(snapshot["root"], snapshot["files"])
        with self.assertRaisesRegex(ValueError, "bounded"):
            native_config.snapshot(self.config, overrides={child: "not bytes"})


if __name__ == "__main__":
    unittest.main()
