"""Exercise the agent contract as a CLI consumer, without desktop activation."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from niri_fx.agent import agent_info, parameter_info, skill_text
from niri_fx.cli import main, parser
from niri_fx.documents import parse_document
from niri_fx.model import Effect


class AgentDiscoveryTests(unittest.TestCase):
    def output(self, *arguments):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(main(list(arguments)), 0)
        return stream.getvalue()

    def test_discovery_does_not_launch_processes_or_probe_a_session(self):
        with (
            patch("subprocess.run", side_effect=AssertionError("Unexpected process")),
            patch("socket.socket", side_effect=AssertionError("Unexpected socket")),
        ):
            info = json.loads(self.output("agent-info"))
            controls = json.loads(self.output("agent-info", "--parameters"))
            self.assertEqual(self.output("agent-info", "--skill").strip(), skill_text().strip())
        self.assertEqual(info, agent_info())
        self.assertEqual(controls, json.loads(json.dumps(parameter_info())))
        # Default values emitted to an agent must form a valid effect without
        # copying a second set of defaults into its own configuration generator.
        Effect(**{key: value["default"] for key, value in controls["effects"].items()})
        for operation in info["operations"].values():
            parser().parse_args(operation["argv"])

    def test_catalog_composition_and_stock_export_preserve_portable_pointer_choice(self):
        catalog = json.loads(self.output("list", "--documents", "--recommended"))
        opening = next(
            name
            for name, doc in catalog.items()
            if doc.get("effect", {}).get("family") == "fragments"
        )
        document = json.loads(
            self.output(
                "profile",
                "--name",
                "Agent Combo",
                "--open-preset",
                opening,
                "--close-preset",
                "spring-wobble",
                "--pointer",
                "gentle",
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "combo.json"
            path.write_text(json.dumps(document))
            normalized = json.loads(self.output("inspect", "--custom", str(path)))
            _, _, profile = parse_document(normalized)
            self.assertEqual(profile.pointer.strength, 0.4)
            self.assertIsNone(profile.resize)
            self.assertIsNone(profile.movement)
            stock = self.output("render", "--custom", str(path))
            self.assertNotIn("pointer-wobble", stock)
            self.assertNotIn("window-resize", stock)
            self.assertNotIn("window-movement", stock)
            self.assertEqual(json.loads(path.read_text()), document)

    def test_compact_catalog_keeps_full_catalog_filters_and_real_document_ids(self):
        for filters in (("--recommended",), ("--family", "fragments"), ("--search", "frost")):
            with self.subTest(filters=filters):
                compact = json.loads(self.output("list", "--summary", *filters))
                full = json.loads(self.output("list", "--documents", *filters))
                self.assertEqual(list(compact), list(full))
                for name, item in compact.items():
                    self.assertEqual(item["name"], full[name]["name"])
                    self.assertNotIn("actions", item)
                    self.assertNotIn("effect", item)
        profiles = json.loads(self.output("list", "--summary", "--profiles"))
        self.assertTrue(profiles)
        self.assertTrue(all(item["kind"] == "profile" for item in profiles.values()))

    @unittest.skipUnless(shutil.which("niri"), "requires real stock Niri validation")
    def test_manifest_review_apply_and_restore_work_against_temporary_files(self):
        operations = agent_info()["operations"]
        with tempfile.TemporaryDirectory(prefix="nirifx-agent-") as temporary:
            root = Path(temporary)
            config, state = root / "config.kdl", root / "state"
            before = b"animations { window-resize { duration-ms 170; }; }\n"
            config.write_bytes(before)
            document = root / "combo.json"
            document.write_text(self.output(*operations["compose"]["argv"]))
            env = os.environ | {"XDG_CONFIG_HOME": str(root), "NIRI_SOCKET": ""}

            def command(argv, expected=0):
                selected = [
                    str(document) if value == "./my-combo.json" else value for value in argv
                ]
                result = subprocess.run(
                    [sys.executable, "-m", "niri_fx", *selected],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                return json.loads(result.stdout) if expected == 0 else result.stderr

            scope = [
                "--config",
                str(config),
                "--state",
                str(state),
                "--inir-root",
                str(root / "no-shell"),
            ]
            reviewed = command([*operations["review"]["argv"], *scope])
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse(state.exists())
            apply = [
                reviewed["plan_sha256"] if value == "REVIEWED_PLAN_SHA256" else value
                for value in operations["apply"]["argv"]
            ]
            result = command([*apply, *scope])
            self.assertTrue(result["changed"])
            config_after = config.read_bytes()
            self.assertNotEqual(config_after, before)
            restored = command(
                ["restore", "--transaction", result["transaction"], "--state", str(state)]
            )
            self.assertTrue(restored["dry_run"])
            self.assertEqual(config.read_bytes(), config_after)
            command(
                [
                    "restore",
                    "--transaction",
                    result["transaction"],
                    "--state",
                    str(state),
                    "--apply",
                ]
            )
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse((root / "nirifx/animations.kdl").exists())
