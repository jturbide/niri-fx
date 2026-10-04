#!/usr/bin/env python3
"""Verify an installed 0.16 wheel upgrade using disposable files and real Niri validation.

The test never imports the checkout's Python package. Its old installation creates
portable JSON, a registered shell profile, favorites and a setup snapshot; the
replacement wheel must preserve those files and restore the old snapshot exactly.
The new Library then saves, reviews, applies and restores that original document.
No desktop session, personal browser profile or live configuration is connected.
"""

import argparse
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = """// An existing user configuration; resize belongs to the user.
hotkey-overlay { skip-at-startup; }
animations { window-resize { duration-ms 170; curve "ease-out-cubic"; }; }
"""


def wheel_version(path):
    with zipfile.ZipFile(path) as archive:
        metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Expected exactly one wheel metadata file")
        value = BytesParser().parsebytes(archive.read(metadata[0]))
    if value["Name"] != "niri-fx":
        raise ValueError("Both wheels must be niri-fx packages")
    return value["Version"]


def verify_checksum(wheel, checksums):
    """Match the exact release asset, without trusting a similarly named local build."""
    entries = {}
    for line in checksums.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (\S+)", line)
        if not match or match[2] in entries:
            raise ValueError("Unsupported or duplicate entry in SHA256SUMS")
        entries[match[2]] = match[1]
    actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if entries.get(wheel.name) != actual:
        raise ValueError("The old wheel does not match its release SHA256SUMS")


def run(command, *, root, env, json_output=False):
    result = subprocess.run(
        [str(value) for value in command],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    return json.loads(result.stdout) if json_output else result.stdout.strip()


def isolated_environment(root):
    env = os.environ.copy()
    # Setup validates files only. Remove inherited session handles so later
    # additions to this test cannot accidentally discover the login compositor.
    for key in (
        "NIRI_SOCKET",
        "WAYLAND_DISPLAY",
        "DISPLAY",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_RUNTIME_DIR",
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
    ):
        env.pop(key, None)
    for key, name in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
    ):
        directory = root / name
        directory.mkdir()
        env[key] = str(directory)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


@contextmanager
def studio(executable, *, root, env, current=False):
    command = [str(executable), "studio", "--target", "standalone", "--no-browser"]
    if current:
        command.append("--active")
    process = subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            ready, _, _ = select.select([process.stdout], [], [], 0.1)
            if ready:
                line = process.stdout.readline()
                if line.startswith("NiriFX Studio: "):
                    yield Session(line.strip().removeprefix("NiriFX Studio: "))
                    return
            if process.poll() is not None:
                raise RuntimeError("The disposable Studio stopped before startup")
        raise RuntimeError("The disposable Studio did not start within 15 seconds")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()


class Session:
    """Keep the local session capability private; never print it in test output."""

    def __init__(self, url):
        self.url = url
        parsed = urlsplit(url)
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self.token = parse_qs(parsed.query)["token"][0]

    def get(self, path=None):
        url = self.url if path is None else self.origin + path + "?token=" + self.token
        with urlopen(url, timeout=15) as response:
            return response.read()

    def catalog(self):
        page = self.get().decode()
        match = re.search(
            r'<script id="effect-catalog" type="application/json">(.*?)</script>', page, re.S
        )
        if not match:
            raise AssertionError("Installed Studio omitted its catalog")
        return json.loads(match[1])

    def post(self, path, value):
        request = Request(
            self.origin + path,
            json.dumps(value).encode(),
            {
                "Content-Type": "application/json",
                "Origin": self.origin,
                "X-NiriFX-Token": self.token,
            },
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            return json.load(response)


def browser_check(session, *, root, env):
    """Load the replacement wheel's real UI in a test-owned Chromium profile."""
    browser_env = dict(
        env,
        NIRIFX_UPGRADE_URL=session.url,
        NIRIFX_BROWSER_HELPER=(ROOT / "scripts/lib/browser.mjs").as_uri(),
    )
    source = """
import assert from 'node:assert/strict';
const {launchBrowser}=await import(process.env.NIRIFX_BROWSER_HELPER);
const browser=await launchBrowser();
try {
  await browser.navigate(process.env.NIRIFX_UPGRADE_URL+'&breakup=0');
  await browser.evaluate(`new Promise((resolve,reject)=>{
    const deadline=Date.now()+10000;
    function check(){
      byId('library-collection').value='customs';
      byId('library-collection').dispatchEvent(new Event('change'));
      const card=document.querySelector('[data-style="custom-saved-night"]');
      if(card){card.click();resolve();}
      else if(Date.now()>deadline)reject(new Error('Saved upgrade profile missing'));
      else setTimeout(check,50);
    }check();
  })`);
  assert.equal(await browser.evaluate('effectDocument().name'),'Saved Night');
  assert.equal(await browser.evaluate('effectDocument().actions.resize'),null);
  assert.equal(await browser.evaluate('effectDocument().actions.movement'),null);
  assert.equal(await browser.evaluate('favorites.includes("zipper")'),true);
  assert.equal(await browser.evaluate('byId("rename-profile").hidden'),false);
  assert.deepEqual(await browser.evaluate(`(()=>{
    const before=JSON.stringify(effectDocument());
    byId('preview-combo').click();
    const plan=niriFxComboPreview.currentPlan;
    niriFxComboPreview.seek(plan.totalMs);
    return {
      actions:plan.stages.filter(stage=>stage.phase==='animation').map(stage=>stage.action),
      state:document.documentElement.dataset.comboState,
      unchanged:before===JSON.stringify(effectDocument())
    };
  })()`),{actions:['open','close'],state:'complete',unchanged:true});
  console.log('PASS installed Library UI, saved old JSON, retained favorite and combo preview');
} finally { await browser.close(); }
"""
    print(run(["node", "--input-type=module", "-e", source], root=root, env=browser_env))


def exercise(old_wheel, new_wheel, *, browser):
    with tempfile.TemporaryDirectory(prefix="nirifx-upgrade-") as directory:
        root = Path(directory)
        env = isolated_environment(root)
        python = root / "venv/bin/python"
        executable = root / "venv/bin/niri-fx"
        run([sys.executable, "-m", "venv", root / "venv"], root=root, env=env)

        def install(wheel):
            run(
                [
                    python,
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    "--force-reinstall",
                    wheel,
                ],
                root=root,
                env=env,
            )
            assert run([executable, "--version"], root=root, env=env) == wheel_version(wheel)
            location = run(
                [python, "-c", "import niri_fx; print(niri_fx.__file__)"], root=root, env=env
            )
            assert Path(location).is_relative_to(root / "venv"), (
                "Imported the checkout instead of the wheel"
            )

        def cli(*arguments, json_output=False):
            return run([executable, *arguments], root=root, env=env, json_output=json_output)

        install(old_wheel)
        config = root / "config/niri/config.kdl"
        config.parent.mkdir()
        config.write_text(BASE)
        run(["niri", "validate", "-c", config], root=root, env=env)
        document = cli(
            "profile",
            "--open-preset",
            "zipper",
            "--close-preset",
            "frost-vanish",
            "--name",
            "Saved Night",
            json_output=True,
        )
        custom = root / "saved-night.json"
        custom.write_text(json.dumps(document, indent=2) + "\n")

        # A synthetic base registry exercises the real old registration command
        # without depending on, launching or modifying an installed shell.
        shell = {
            "active": "base",
            "presets": [
                {
                    "id": "base",
                    "types": {
                        "workspace-switch": {"spring": [0.9, 700, 0.0001]},
                        "window-resize": {"duration-ms": 170, "curve": "ease-out-cubic"},
                    },
                }
            ],
        }
        helper = root / "data/inir/scripts/niri-config.py"
        helper.parent.mkdir(parents=True)
        helper.write_text("print(" + repr(json.dumps(shell)) + ")\n")
        registry = root / "config/inir/niri-animation-presets.json"
        registry.parent.mkdir()
        registry.write_text(
            json.dumps({"presets": [{"id": "other-provider", "name": "User Style"}]}) + "\n"
        )
        cli("register", "--custom", custom)
        saved = json.loads(registry.read_text())["presets"]
        assert saved[0]["id"] == "other-provider"
        assert saved[1]["profile"] == document
        assert saved[1]["types"]["window-resize"] == shell["presets"][0]["types"]["window-resize"]

        with studio(executable, root=root, env=env) as session:
            assert session.post("/preferences", {"favorites": ["zipper", "frost-vanish"]})["ok"]
            assert session.catalog()["preferences"]["favorites"] == ["frost-vanish", "zipper"]
        old_setup = cli(
            "setup",
            "--target",
            "standalone",
            "--custom",
            custom,
            "--no-launcher",
            "--apply",
            json_output=True,
        )
        assert old_setup["changed"]
        include = config.parent / "nirifx/animations.kdl"
        assert "window-resize" not in include.read_text()
        state = root / "state/niri-fx"
        # Preserve every snapshot byte as well as documents, preferences and
        # active files; installation must not perform a silent migration/Apply.
        protected = [custom, registry, config, include, *state.rglob("*")]
        before = {path: path.read_bytes() for path in protected if path.is_file()}
        install(new_wheel)
        assert all(path.read_bytes() == content for path, content in before.items())
        assert cli("inspect", "--custom", custom, json_output=True) == document
        cli("restore", "--transaction", old_setup["transaction"], "--apply", json_output=True)
        assert config.read_text() == BASE and not include.exists()
        assert registry.read_bytes() == before[registry]

        with studio(executable, root=root, env=env, current=True) as session:
            assert session.catalog()["preferences"]["favorites"] == ["frost-vanish", "zipper"]
            assert session.post("/store", {"document": document, "expected": None})["changed"]
            listing = json.loads(session.get("/library"))
            assert listing["managed"]["custom-saved-night"]["document"] == document
            assert not listing["restore"] and config.read_text() == BASE
            if browser:
                browser_check(session, root=root, env=env)
            selection = {"document": document, "allow_resize": False, "allow_movement": False}
            review = session.post("/review", selection)
            assert config.read_text() == BASE and not include.exists()
            applied = session.post(
                "/apply", {"selection": selection, "expected": review["plan_sha256"]}
            )
            assert applied["changed"] and "window-resize" not in include.read_text()
            run(["niri", "validate", "-c", config], root=root, env=env)
            assert json.loads(session.get("/library"))["active"] == document
            assert not session.post("/restore", {})["dry_run"]
            assert config.read_text() == BASE and not include.exists()
            assert (
                json.loads(session.get("/library"))["managed"]["custom-saved-night"]["document"]
                == document
            )
        assert registry.read_bytes() == before[registry]
        assert custom.read_bytes() == before[custom]
        assert (state / "studio-preferences.json").read_bytes() == before[
            state / "studio-preferences.json"
        ]
        print(
            f"PASS {wheel_version(old_wheel)} -> {wheel_version(new_wheel)}: installed CLI/Studio, "
            "old JSON and shell registry, favorites, exact old snapshot restore, "
            "Library Save/Review/Apply/Restore, user resize preserved"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-wheel", type=Path, required=True, help="Official v0.16.0 release wheel"
    )
    parser.add_argument("--to-wheel", type=Path, required=True, help="Newly built candidate wheel")
    parser.add_argument("--checksums", type=Path, required=True, help="v0.16.0 release SHA256SUMS")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Also load the installed UI in isolated Chromium (Node 22+)",
    )
    args = parser.parse_args()
    if not shutil.which("niri"):
        parser.error("Install stock Niri to validate the temporary configurations")
    if args.browser and not shutil.which("node"):
        parser.error("--browser requires Node 22 or newer and Chromium/Chrome")
    old_wheel, new_wheel = args.from_wheel.resolve(), args.to_wheel.resolve()
    if wheel_version(old_wheel) != "0.16.0":
        parser.error("--from-wheel must be the official 0.16.0 release wheel")
    verify_checksum(old_wheel, args.checksums.resolve())
    exercise(old_wheel, new_wheel, browser=args.browser)


if __name__ == "__main__":
    main()
