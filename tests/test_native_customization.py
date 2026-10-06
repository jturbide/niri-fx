"""Managed customization retains a baseline and changes only the next login."""

import io
import json
import os
import shutil
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import test_native_session

from niri_fx import native_build, native_customization, native_session, setup
from niri_fx.catalog import PROFILES, title
from niri_fx.cli import main, parser
from niri_fx.documents import effect_document, parse_document
from niri_fx.fragment_motion import PRESETS
from niri_fx.model import Effect
from niri_fx.pointer import PointerWobble
from niri_fx.presets import PRESETS as STYLE_PRESETS
from niri_fx.profiles import Profile
from niri_fx.storage import digest


class NativeCustomizationTests(unittest.TestCase):
    def setUp(self):
        # Compose the synthetic desktop-build fixture without rerunning its tests.
        self.fixture = test_native_session.NativeSessionTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.destination
        self.validator = self.fixture.validator

    def stage(self, *, includes=False, variant="fragment"):
        record = self.fixture.record
        record["unmodified"] = variant == "unmodified"
        for name, field in native_build.PATCH_FIELDS.items():
            if name in native_build.STACKS[variant]:
                record[field] = native_build.digest(self.fixture.repository / "experimental" / name)
            else:
                record.pop(field, None)
        record["native_build"] = native_build.metadata(
            record,
            variant=variant,
            lock_sha256=native_build.digest(self.fixture.source / "Cargo.lock"),
            target="x86_64-unknown-linux-gnu",
            features=["default", *native_build.DESKTOP_FEATURES],
            rustc_verbose=f"{record['rustc']}\nhost: x86_64-unknown-linux-gnu",
        )
        self.fixture.save_record()
        if includes:
            self.fixture.config.write_text('layout {}\ninclude "colors.kdl"\nanimations { off; }\n')
            (self.fixture.root / "colors.kdl").write_text('environment { EXAMPLE "saved"; }\n')
        plan = self.fixture.plan(snapshot_includes=includes)
        setup.apply_plan(plan, self.fixture.stage_state)
        self.validator.reset_mock()
        return plan["selection"]["bundle_id"]

    def plan(self, bundle, profile=None, *, fragment_preset=None):
        document = effect_document("My desktop", Profile() if profile is None else profile)
        return native_customization.configure_plan(
            self.root, bundle, document, fragment_preset=fragment_preset
        )

    def apply(self, plan):
        return native_customization.apply_native(
            plan, self.root, expected=setup.plan_fingerprint(plan)
        )

    def report(self, plan):
        return native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])

    def recipe_and_files(self, plan):
        folder = self.root / "bundles" / plan["selection"]["bundle_id"]
        receipt = json.loads((folder / "bundle.json").read_bytes())
        return receipt["customization"], {
            name: (folder / name).read_bytes() for name in receipt["config_files"]
        }

    def test_separate_swap_keeps_move_response_and_preserve_removes_only_swap_override(self):
        baseline = self.stage()
        profile = Profile(movement=PRESETS["tear"].effect, swap=STYLE_PRESETS["pixel-relay"])
        plan = self.plan(baseline, profile, fragment_preset="tear")
        self.apply(plan)
        recipe, files = self.recipe_and_files(plan)
        overlay = files[recipe["overlay_file"]].decode()
        self.assertEqual(overlay.count("    window-swap {"), 1)
        self.assertEqual(overlay.count("    window-movement {"), 1)
        self.assertIn("fragment-motion {", overlay.split("window-swap")[0])
        self.assertNotIn("fragment-motion {", overlay.split("window-swap")[1])
        self.assertEqual(recipe["document"]["schema"], 3)
        self.assertEqual(
            self.report(plan)["customization"]["document"], profile.document("My desktop")
        )
        preserve = self.plan(
            plan["selection"]["bundle_id"],
            Profile(movement=profile.movement),
            fragment_preset="tear",
        )
        self.apply(preserve)
        recipe, files = self.recipe_and_files(preserve)
        self.assertNotIn("window-swap", files[recipe["overlay_file"]].decode())
        self.assertIn("fragment-motion", files[recipe["overlay_file"]].decode())
        self.assertEqual(recipe["document"]["schema"], 2)

    def test_older_compositor_refuses_swap_before_any_write(self):
        baseline = self.stage(variant="movement")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "updated NiriFX session"):
            self.plan(baseline, Profile(swap="off"))
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_review_is_read_only_and_apply_selects_an_independent_pair(self):
        baseline = self.stage(includes=True)
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        plan = self.plan(baseline, Profile(open=Effect(), close="off"))
        self.validator.assert_not_called()
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse(Path(plan["validation_config"]).exists())
        self.assertEqual(Path(plan["changes"][-1]["target"]), self.root / "selection.json")
        self.assertEqual(plan["activation"], "next-login")
        self.assertNotIn("movement", plan)
        result = self.apply(plan)
        self.assertNotIn("restore", result)
        self.assertEqual(result["activation"], "next-login")
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        report = self.report(plan)
        self.assertEqual(report["config_file_count"], 3)
        self.assertEqual(report["runtime_acceptance"], "not_assessed")
        self.validator.assert_called_once_with(report["config"], report["binary"])
        original = native_session.inspect_bundle(self.root, baseline)
        self.assertNotEqual(
            Path(original["binary"]).stat().st_ino, Path(report["binary"]).stat().st_ino
        )
        self.assertEqual(native_session.load_selection(self.root)["selected"], report["bundle_id"])
        self.assertIsNone(native_session.load_selection(self.root)["previous"])
        self.assertIn("animations { off; }", Path(report["config"]).read_text())
        self.assertTrue(any("Global animations off" in note for note in plan["notes"]))

    def test_plain_schema_one_has_no_recipe_and_customization_can_be_reopened(self):
        baseline = self.stage()
        self.assertIsNone(native_customization.read_recipe(self.root, baseline))
        profile = Profile(open=Effect(), close="off", resize="off")
        plan = self.plan(baseline, profile)
        self.apply(plan)
        recipe = native_customization.read_recipe(self.root, plan["selection"]["bundle_id"])
        self.assertEqual(
            recipe,
            {
                "schema": 1,
                "baseline_bundle": baseline,
                "document": effect_document("My desktop", profile),
                "fragment_preset": None,
            },
        )
        saved, files = self.recipe_and_files(plan)
        overlay = files[saved["overlay_file"]].decode()
        self.assertIn("window-open {", overlay)
        self.assertIn("window-close {\n        off", overlay)
        self.assertIn("window-resize {\n        off", overlay)
        self.assertNotIn("window-movement {", overlay)

    def test_repeated_edits_replace_override_and_preserve_original_baseline(self):
        baseline = self.stage(includes=True)
        first = self.plan(
            baseline,
            Profile(open=Effect(), movement=PRESETS["tear"].effect),
            fragment_preset="tear",
        )
        self.apply(first)
        second = self.plan(first["selection"]["bundle_id"], Profile(close="off"))
        self.apply(second)
        first_recipe, first_files = self.recipe_and_files(first)
        second_recipe, second_files = self.recipe_and_files(second)
        self.assertEqual(second_recipe["baseline_bundle"], baseline)
        self.assertEqual(first_recipe["baseline_files"], second_recipe["baseline_files"])
        self.assertEqual(set(first_files), set(second_files))
        self.assertEqual(first_files["config.kdl"], second_files["config.kdl"])
        overlay = second_files[second_recipe["overlay_file"]].decode()
        self.assertNotIn("window-open {", overlay)
        self.assertNotIn("window-movement {", overlay)
        self.assertNotIn("fragment-motion", overlay)
        self.assertEqual(self.report(second)["config_file_count"], 3)
        self.assertEqual(
            native_session.load_selection(self.root)["previous"], first["selection"]["bundle_id"]
        )

    def test_edit_survives_removal_of_original_baseline_and_candidate(self):
        baseline = self.stage(includes=True)
        first = self.plan(baseline, Profile(open="off"))
        self.apply(first)
        shutil.rmtree(self.root / "bundles" / baseline)
        shutil.rmtree(self.fixture.candidate)
        shutil.rmtree(self.fixture.repository)
        second = self.plan(first["selection"]["bundle_id"], Profile(close="off"))
        self.apply(second)
        self.assertEqual(self.report(second)["customization"]["baseline_bundle"], baseline)

    def test_fragment_choices_bind_both_canonical_material_and_response(self):
        baseline = self.stage()
        choices = native_customization.fragment_choices()
        self.assertEqual(set(choices), {"gentle", "tear", "cascade"})
        for name, preset in PRESETS.items():
            with self.subTest(preset=name):
                self.assertEqual(choices[name]["effect"], asdict(preset.effect))
                plan = self.plan(baseline, Profile(movement=preset.effect), fragment_preset=name)
                self.apply(plan)
                recipe, files = self.recipe_and_files(plan)
                overlay = files[recipe["overlay_file"]].decode()
                self.assertIn("fragment-motion {", overlay)
                self.assertIn("preserve-pointer", overlay)
                self.assertEqual(recipe["fragment_preset"], name)
        for profile in (Profile(), Profile(movement="off"), Profile(movement=Effect())):
            with self.assertRaisesRegex(ValueError, "matching canonical movement material"):
                self.plan(baseline, profile, fragment_preset="tear")
        for unknown in ("unknown", [], True):
            with self.assertRaisesRegex(ValueError, "known continuous fragment"):
                self.plan(baseline, fragment_preset=unknown)

    def test_variant_gate_is_about_retained_binary_not_running_desktop(self):
        for variant in native_build.STACKS:
            with self.subTest(variant=variant):
                baseline = self.stage(variant=variant)
                self.plan(baseline, Profile(open="off"))
                if variant == "unmodified":
                    with self.assertRaisesRegex(ValueError, "movement-capable"):
                        self.plan(baseline, Profile(movement="off"))
                else:
                    self.plan(baseline, Profile(movement="off"))
                if variant not in ("pointer", "fragment"):
                    with self.assertRaisesRegex(ValueError, "pointer-capable"):
                        self.plan(baseline, Profile(pointer=PointerWobble(strength=0)))
                else:
                    self.plan(baseline, Profile(pointer=PointerWobble(strength=0)))
                if variant != "fragment":
                    with self.assertRaisesRegex(ValueError, "fragment build|movement-capable"):
                        self.plan(
                            baseline,
                            Profile(movement=PRESETS["tear"].effect),
                            fragment_preset="tear",
                        )
        self.validator.assert_not_called()

    def test_pointer_only_override_preserves_movement_and_off_is_explicit(self):
        baseline = self.stage()
        plan = self.plan(baseline, Profile(pointer=PointerWobble(strength=0)))
        self.apply(plan)
        recipe, files = self.recipe_and_files(plan)
        overlay = files[recipe["overlay_file"]].decode()
        self.assertIn("preserve-movement", overlay)
        self.assertIn("pointer-wobble {\n            strength 0", overlay)
        self.assertNotIn("custom-shader", overlay)

    def test_plain_profile_movement_and_cleared_preset_use_timed_shader_only(self):
        baseline = self.stage()
        plain = self.plan(baseline, Profile(movement=Effect()))
        self.apply(plain)
        recipe, files = self.recipe_and_files(plain)
        self.assertNotIn(b"nirifx-fragment-motion", files[recipe["overlay_file"]])
        continuous = self.plan(
            baseline, Profile(movement=PRESETS["tear"].effect), fragment_preset="tear"
        )
        self.apply(continuous)
        recipe, files = self.recipe_and_files(continuous)
        self.assertIn(b"nirifx-fragment-motion: 3", files[recipe["overlay_file"]])
        cleared = self.plan(
            continuous["selection"]["bundle_id"], Profile(movement=PRESETS["tear"].effect)
        )
        self.apply(cleared)
        recipe, files = self.recipe_and_files(cleared)
        self.assertIsNone(recipe["fragment_preset"])
        self.assertNotIn(b"nirifx-fragment-motion", files[recipe["overlay_file"]])
        self.assertNotIn(b"fragment-motion {", files[recipe["overlay_file"]])
        self.assertIn(b"custom-shader", files[recipe["overlay_file"]])

    def test_selector_rollback_retains_both_pairs_and_supports_previous_none(self):
        baseline = self.stage()
        first = self.plan(baseline, Profile(open="off"))
        self.apply(first)
        self.apply(native_session.rollback_plan(self.root))
        self.assertIsNone(native_session.load_selection(self.root)["selected"])
        self.report(first)
        self.apply(native_session.rollback_plan(self.root))
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], first["selection"]["bundle_id"]
        )
        native_session.inspect_bundle(self.root, baseline)
        with self.assertRaisesRegex(ValueError, "native rollback"):
            setup.restore(self.fixture.selection_state, apply=True)

    def test_reapplying_same_recipe_is_idempotent_and_keeps_rollback(self):
        baseline = self.stage()
        self.fixture.apply_selection(native_session.select_plan(self.root, baseline))
        first = self.plan(baseline, Profile(close="off"))
        self.apply(first)
        second = self.plan(first["selection"]["bundle_id"], Profile(close="off"))
        self.assertEqual(first["selection"]["bundle_id"], second["selection"]["bundle_id"])
        self.assertEqual(second["changes"], [])
        self.apply(second)
        self.assertEqual(native_session.load_selection(self.root)["previous"], baseline)

    def test_failed_validation_restores_selector_and_removes_only_new_bytes(self):
        baseline = self.stage()
        self.fixture.apply_selection(native_session.select_plan(self.root, baseline))
        plan = self.plan(baseline, Profile(open="off"))
        self.validator.side_effect = ValueError("synthetic invalid config")
        with self.assertRaisesRegex(ValueError, "synthetic invalid"):
            self.apply(plan)
        self.assertEqual(native_session.load_selection(self.root)["selected"], baseline)
        folder = self.root / "bundles" / plan["selection"]["bundle_id"]
        self.assertFalse(any(p.is_file() for p in folder.rglob("*")))
        native_session.inspect_bundle(self.root, baseline)
        self.validator.side_effect = None
        self.apply(self.plan(baseline, Profile(open="off")))

    def test_selector_created_or_changed_after_review_refuses_before_writing(self):
        baseline = self.stage()
        plan = self.plan(baseline, Profile(open="off"))
        self.fixture.apply_selection(native_session.select_plan(self.root, baseline))
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.apply(plan)
        self.assertFalse(Path(plan["validation_config"]).exists())
        refreshed = self.plan(baseline, Profile(open="off"))
        self.apply(native_session.rollback_plan(self.root))
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.apply(refreshed)

    def test_review_fingerprint_binds_document_and_native_response(self):
        baseline = self.stage()
        one = self.plan(baseline, Profile(open="off"))
        two = self.plan(baseline, Profile(close="off"))
        with self.assertRaisesRegex(ValueError, "review|plan"):
            native_customization.apply_native(two, self.root, expected=setup.plan_fingerprint(one))
        self.assertFalse(Path(two["validation_config"]).exists())

    def test_observed_baseline_content_permissions_and_special_file_drift_refuse(self):
        baseline = self.stage()
        report = native_session.inspect_bundle(self.root, baseline)
        path = Path(report["config"])
        data = path.read_bytes()
        for mutation in ("content", "mode", "fifo", "symlink"):
            with self.subTest(mutation=mutation):
                plan = self.plan(baseline, Profile(open="off"))
                if mutation == "content":
                    path.write_text("animations { off; }\n")
                elif mutation == "mode":
                    path.chmod(0o644)
                else:
                    path.unlink()
                    if mutation == "fifo":
                        os.mkfifo(path)
                    else:
                        path.symlink_to(self.fixture.config)
                with self.assertRaises(ValueError):
                    self.apply(plan)
                self.assertFalse(Path(plan["validation_config"]).exists())
                path.unlink()
                path.write_bytes(data)
                path.chmod(0o600)

    def test_saved_recipe_and_baseline_backup_are_bound_by_identity_and_hashes(self):
        baseline = self.stage(includes=True)
        plan = self.plan(baseline, Profile(open="off"))
        self.apply(plan)
        folder = Path(self.report(plan)["config"]).parent
        marker = folder / "bundle.json"
        original = marker.read_bytes()
        receipt = json.loads(original)
        receipt["customization"]["document"]["name"] = "Changed recipe"
        marker.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "identity"):
            self.report(plan)
        marker.write_bytes(original)
        saved_root = folder / native_customization.BASELINE_ROOT
        saved_root.write_text("animations {}\n")
        with self.assertRaisesRegex(ValueError, "baseline ownership"):
            self.report(plan)

    def test_malformed_recipe_and_reserved_or_external_config_paths_refuse(self):
        baseline = self.stage()
        plan = self.plan(baseline)
        self.apply(plan)
        recipe, files = self.recipe_and_files(plan)
        baseline_data = Path(
            native_session.inspect_bundle(self.root, baseline)["config"]
        ).read_bytes()
        mutations = [
            {"schema": True},
            {"baseline_bundle": "not an id"},
            {"overlay_file": "config.kdl"},
            {"baseline_files": {}},
            {"overlay_file": "customization/base-config.kdl"},
            {"baseline_files": {"config.kdl": digest(baseline_data), "../outside": "a" * 64}},
            {"fragment_preset": "arbitrary"},
            {"unexpected": True},
        ]
        for fields in mutations:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                native_customization.validate_customization(
                    recipe | fields, files, baseline_data, variant="fragment"
                )

    def test_arbitrary_paths_shaders_unknown_fields_and_non_json_documents_refuse(self):
        baseline = self.stage()
        document = effect_document("My desktop", Profile())
        cases = [
            document | {"path": "/tmp/config.kdl"},
            document | {"shader": "arbitrary GLSL"},
            document | {"name": "x" * 20000},
            document | {"name": float("nan")},
            {"not": object()},
        ]
        for data in cases:
            with self.subTest(data=repr(data)[:80]), self.assertRaises(ValueError):
                native_customization.configure_plan(self.root, baseline, data)
        self.validator.assert_not_called()

    def test_existing_incomplete_destination_is_not_overwritten(self):
        baseline = self.stage()
        plan = self.plan(baseline)
        folder = Path(plan["validation_config"]).parent
        folder.mkdir()
        (folder / "unowned").write_text("Keep me")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.plan(baseline)
        self.assertEqual((folder / "unowned").read_text(), "Keep me")

    def test_deepest_supported_baseline_keeps_its_depth_after_repeated_edits(self):
        self.fixture.config.write_text('include "child1.kdl"\n')
        for index in range(1, 10):
            (self.fixture.root / f"child{index}.kdl").write_text(
                f'include "child{index + 1}.kdl"\n' if index < 9 else "animations {}\n"
            )
        stage = self.fixture.plan(snapshot_includes=True)
        setup.apply_plan(stage, self.fixture.stage_state)
        baseline = stage["selection"]["bundle_id"]
        first = self.plan(baseline, Profile(open="off"))
        self.apply(first)
        second = self.plan(first["selection"]["bundle_id"], Profile(close="off"))
        self.apply(second)
        self.assertEqual(self.report(second)["config_file_count"], 11)

    def test_full_baseline_file_budget_refuses_extra_override_without_writes(self):
        self.fixture.config.write_text("".join(f'include "child{i}.kdl"\n' for i in range(127)))
        for index in range(127):
            (self.fixture.root / f"child{index}.kdl").write_text("// retained child\n")
        stage = self.fixture.plan(snapshot_includes=True)
        setup.apply_plan(stage, self.fixture.stage_state)
        baseline = stage["selection"]["bundle_id"]
        with self.assertRaisesRegex(ValueError, "file count"):
            self.plan(baseline)
        self.assertFalse((self.root / "selection.json").exists())

    def test_cli_review_apply_and_plan_mismatch_are_symmetric(self):
        baseline = self.stage()
        path = self.fixture.root / "profile.json"
        path.write_text(json.dumps(effect_document("My desktop", Profile(open="off"))))
        args = ["native", "configure", baseline, "--root", str(self.root), "--document", str(path)]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        reviewed = json.loads(output.getvalue())
        self.assertTrue(reviewed["dry_run"])
        self.assertEqual(reviewed["activation"], "next-login")
        self.validator.assert_not_called()
        self.assertFalse((self.root / "selection.json").exists())
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([*args, "--apply", "--expect-plan", reviewed["plan_sha256"]]), 0)
        applied = json.loads(output.getvalue())
        self.assertFalse(applied["dry_run"])
        self.assertNotIn("restore", applied)
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], reviewed["selection"]["bundle_id"]
        )
        self.assertIn("running session is unchanged", applied["next_step"])

    def test_cli_prefabs_are_explicit_and_do_not_enable_additional_actions(self):
        baseline = self.stage()
        for flag, key, effect in (
            ("--profile", "fragments-motion", PROFILES["fragments-motion"]),
            ("--preset", "balanced", STYLE_PRESETS["balanced"]),
        ):
            with self.subTest(flag=flag):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(
                        main(
                            ["native", "configure", baseline, "--root", str(self.root), flag, key]
                        ),
                        0,
                    )
                plan = json.loads(output.getvalue())
                self.assertEqual(plan["selection"]["document"], effect_document(title(key), effect))
                self.assertIsNone(plan["selection"]["fragment_preset"])
                self.assertFalse((self.root / "selection.json").exists())
        self.validator.assert_not_called()

    def test_cli_explicit_fragment_choice_supplies_material_and_applies_reviewed_plan(self):
        baseline = self.stage()
        args = [
            "native",
            "configure",
            baseline,
            "--root",
            str(self.root),
            "--profile",
            "fragments-motion",
            "--fragment-preset",
            "tear",
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        reviewed = json.loads(output.getvalue())
        document = reviewed["selection"]["document"]
        _, _, configured = parse_document(document)
        baseline_profile = PROFILES["fragments-motion"]
        self.assertEqual(configured.open, baseline_profile.open)
        self.assertEqual(configured.close, baseline_profile.close)
        self.assertEqual(configured.resize, baseline_profile.resize)
        self.assertEqual(configured.motion, baseline_profile.motion)
        self.assertEqual(configured.movement, PRESETS["tear"].effect)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([*args, "--apply", "--expect-plan", reviewed["plan_sha256"]]), 0)
        recipe = native_customization.read_recipe(self.root, reviewed["selection"]["bundle_id"])
        self.assertEqual(recipe["document"], document)
        self.assertIsNone(recipe["fragment_preset"])
        self.assertEqual(recipe["document"]["fragment_motion"], asdict(PRESETS["tear"].settings))

    def test_cli_choices_are_mutually_exclusive_and_have_no_implicit_default(self):
        for flags in (
            [],
            ["--preset", "balanced", "--profile", "fragment-flow"],
            ["--document", "profile.json", "--preset", "balanced"],
            ["--fragment-preset", "tear"],
        ):
            with (
                self.subTest(flags=flags),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                parser().parse_args(["native", "configure", "a" * 64, *flags])

    def test_explicit_fragment_expansion_preserves_effect_resize_and_profile_metadata(self):
        for resize in (False, True):
            effect = Effect(resize=resize)
            doc = effect_document("Custom style", effect)
            expanded = native_customization.configuration_document(
                document=doc, fragment_preset="gentle"
            )
            _, _, profile = parse_document(expanded)
            self.assertEqual(profile.open, Effect())
            self.assertEqual(profile.close, Effect())
            self.assertEqual(profile.resize, Effect() if resize else None)
            self.assertEqual(profile.movement, PRESETS["gentle"].effect)
            self.assertEqual(doc, effect_document("Custom style", effect))
        original = Profile(open="off", resize="off", pointer=PointerWobble(strength=0))
        expanded = native_customization.configuration_document(
            document=effect_document("Preserve choices", original), fragment_preset="cascade"
        )
        _, _, profile = parse_document(expanded)
        self.assertEqual(profile.open, "off")
        self.assertIsNone(profile.close)
        self.assertEqual(profile.resize, "off")
        self.assertEqual(profile.pointer, original.pointer)
        self.assertEqual(profile.movement, PRESETS["cascade"].effect)

    def test_selection_helper_rejects_unknown_or_conflicting_choices(self):
        for values in (
            {},
            {"preset": "unknown"},
            {"profile": []},
            {"profile": "fragment-flow", "preset": "balanced"},
            {"preset": "balanced", "fragment_preset": "unknown"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                native_customization.configuration_document(**values)

    def test_native_preset_discovery_needs_no_bundle_and_is_read_only(self):
        for flags in ([], ["--text"]):
            output = io.StringIO()
            with (
                patch.object(
                    native_session,
                    "inspect_bundle",
                    side_effect=AssertionError("No bundle inspection"),
                ),
                redirect_stdout(output),
            ):
                self.assertEqual(main(["native", "presets", *flags]), 0)
            if flags:
                self.assertTrue(all(name in output.getvalue() for name in PRESETS))
            else:
                self.assertEqual(
                    json.loads(output.getvalue()), native_customization.fragment_choices()
                )
        self.assertFalse(self.root.exists())
        self.validator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
