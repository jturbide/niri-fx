"""Package upgrades preserve recipes, shared settings and recovery choices."""

import json
import unittest
from pathlib import Path

import test_native_install

from niri_fx import native_customization, native_session, native_shared, setup
from niri_fx.documents import effect_document
from niri_fx.model import Effect
from niri_fx.native_upgrade import upgrade_plan
from niri_fx.profiles import Profile
from niri_fx.storage import digest


class NativeUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_install.NativeInstallTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.candidate = self.fixture.candidate
        original = self.fixture.plan()
        self.fixture.apply(original)
        self.original = original["selection"]["bundle_id"]

    def apply(self, plan):
        return setup.apply_plan(plan, self.root / "state/selection", setup.plan_fingerprint(plan))

    def newer_candidate(self):
        fixture = self.fixture.fixture
        fixture.binary.write_bytes(b"new synthetic executable, never run\n")
        fixture.record["binary_sha256"] = digest(fixture.binary.read_bytes())
        fixture.save_record()

    def customize(self):
        document = effect_document("My settings", Profile(open=Effect(), close="off", swap="off"))
        plan = native_customization.configure_plan(self.root, self.original, document)
        self.apply(plan)
        return native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])

    def test_plain_upgrade_retains_previous_and_validates_new_binary(self):
        old = native_session.inspect_bundle(self.root, self.original)
        self.newer_candidate()
        plan = upgrade_plan(self.root, self.candidate)
        self.assertEqual(plan["selection"]["previous"], self.original)
        self.assertFalse(Path(plan["validation_binary"]).exists())
        self.apply(plan)
        new = native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])
        self.assertNotEqual(old["binary_sha256"], new["binary_sha256"])
        self.assertEqual(Path(old["config"]).read_bytes(), Path(new["config"]).read_bytes())
        self.fixture.validator.assert_called_with(new["config"], new["binary"])
        self.assertEqual(upgrade_plan(self.root, self.candidate)["changes"], [])
        self.apply(native_session.rollback_plan(self.root))
        self.assertEqual(native_session.load_selection(self.root)["selected"], self.original)

    def test_customization_and_baseline_bytes_survive_without_preset_regeneration(self):
        old = self.customize()
        original_files = native_customization._owned_files(old)
        self.newer_candidate()
        plan = upgrade_plan(self.root, self.candidate)
        self.apply(plan)
        new = native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])
        files = native_customization._owned_files(new)
        receipt = json.loads(original_files["bundle.json"])
        for name in [*receipt["config_files"], native_customization.BASELINE_ROOT]:
            self.assertEqual(files[name], original_files[name])
        self.assertEqual(old["customization"], new["customization"])
        # Subsequent editing still resolves the retained baseline on the new build.
        edit = native_customization.configure_plan(
            self.root, new["bundle_id"], effect_document("Preserve", Profile())
        )
        self.apply(edit)
        edited = native_session.inspect_bundle(self.root, edit["selection"]["bundle_id"])
        self.assertEqual(edited["binary_sha256"], new["binary_sha256"])

    def test_shared_upgrade_keeps_effects_and_current_external_settings(self):
        old = self.customize()
        config = self.fixture.fixture.config
        stock = config.parent / "stock-niri"
        stock.write_bytes(b"synthetic stock validator, never run")
        stock.chmod(0o755)
        shared_plan = native_shared.share_plan(
            self.root, old["bundle_id"], config, stock_binary=stock
        )
        self.apply(shared_plan)
        old = native_session.inspect_bundle(self.root, shared_plan["selection"]["bundle_id"])
        assets = native_shared._assets(old)
        config.write_bytes(config.read_bytes().replace(b"animations {}", b"layout { gaps 17; }"))
        source_bytes = config.read_bytes()
        self.newer_candidate()
        plan = upgrade_plan(self.root, self.candidate)
        self.assertEqual(config.read_bytes(), source_bytes)
        self.assertEqual(plan["selection"]["base_bundle"], old["bundle_id"])
        self.assertFalse(Path(plan["validation_binary"]).exists())
        self.apply(plan)
        new = native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])
        self.assertEqual(config.read_bytes(), source_bytes)
        self.assertEqual(new["customization"], old["customization"])
        self.assertNotEqual(new["config"], old["config"])
        self.assertEqual(native_shared._assets(new)["stock"], assets["stock"])
        self.assertEqual(native_shared._assets(new)["native"], assets["native"])
        self.assertEqual(native_shared.inspect_settings(new)["status"], "current")
        self.assertEqual(upgrade_plan(self.root, self.candidate)["changes"], [])
        self.apply(native_session.rollback_plan(self.root))
        rollback = native_session.inspect_bundle(
            self.root, native_session.load_selection(self.root)["selected"]
        )
        self.assertEqual(rollback["binary_sha256"], old["binary_sha256"])
        self.assertEqual(config.read_bytes(), source_bytes)

    def test_candidate_drift_after_review_refuses_without_selecting(self):
        self.newer_candidate()
        plan = upgrade_plan(self.root, self.candidate)
        self.fixture.fixture.binary.write_bytes(b"changed after review")
        with self.assertRaises((ValueError, RuntimeError)):
            self.apply(plan)
        self.assertEqual(native_session.load_selection(self.root)["selected"], self.original)

    def test_failed_validation_restores_selection_and_retains_original_bytes(self):
        old = native_session.inspect_bundle(self.root, self.original)
        self.newer_candidate()
        plan = upgrade_plan(self.root, self.candidate)
        self.fixture.validator.side_effect = ValueError("synthetic validation failure")
        with self.assertRaisesRegex(ValueError, "synthetic validation failure"):
            self.apply(plan)
        self.assertEqual(native_session.load_selection(self.root)["selected"], self.original)
        self.assertEqual(
            native_session.inspect_bundle(self.root, self.original)["binary_sha256"],
            old["binary_sha256"],
        )
        self.fixture.validator.side_effect = None
        self.apply(upgrade_plan(self.root, self.candidate))
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], plan["selection"]["bundle_id"]
        )


if __name__ == "__main__":
    unittest.main()
