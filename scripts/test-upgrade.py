#!/usr/bin/env python3
"""Verify an installed release wheel upgrade using disposable files and real Niri validation.

The test never imports the checkout's Python package. Its old installation creates
portable JSON, registered shell entries, saved Library profiles, favorites and
both CLI and Library Apply snapshots. The replacement wheel must preserve every
file and restore both histories exactly before exercising optional native metadata.
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
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
# Each source release must create its own real documents and restore snapshots.
# Record its schema explicitly so a changed source artifact cannot silently turn
# an upgrade check into a current-format round trip.
SOURCE_SCHEMAS = {"0.17.0": 1, "0.18.0": 1, "0.19.0": 2}
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


def snapshot_files(*paths):
    """Include added/deleted files in preservation checks, not just known file contents."""
    files = (entry for path in paths for entry in (path.rglob("*") if path.is_dir() else [path]))
    return {path: path.read_bytes() for path in files if path.is_file()}


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

    def rejected(self, path, value, message):
        """Require the intended guard, rather than accepting any failed request."""
        try:
            self.post(path, value)
        except HTTPError as error:
            with error:
                body = json.load(error)
                assert error.code == 400 and message in body.get("error", ""), body
        else:
            raise AssertionError("A request that should have been rejected was accepted")

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
    # Chromium may create crash-report/cache files outside --user-data-dir.
    # Keep those separate from the application trees checked for preservation.
    for key, name in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_RUNTIME_DIR", "runtime"),
    ):
        path = root / "browser" / name
        path.mkdir(mode=0o700, parents=True)
        browser_env[key] = str(path)
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
  assert.equal(await browser.evaluate('favorites.includes("custom-saved-night")'),true);
  assert.equal(await browser.evaluate('effectDocument().pointer ?? null'),null);
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
  assert.equal(await browser.evaluate('effectDocument().schema'),2);
  assert.deepEqual(await browser.evaluate(`
    ['open','close','resize','movement','pointer'].map(action=>byId('combo-'+action+'-mode').value)
  `),['style','style','preserve','preserve','preserve']);
  const modes=await browser.evaluate(`(()=>{
    for(const [action,value] of Object.entries({open:'preserve',close:'off',resize:'off',movement:'off',pointer:'off'})){
      const select=byId('combo-'+action+'-mode');
      select.value=value;select.dispatchEvent(new Event('change'));
    }
    return effectDocument();
  })()`);
  assert.deepEqual(modes.actions,{open:null,close:'off',resize:'off',movement:'off'});
  assert.equal(modes.pointer.strength,0);
  assert.deepEqual(await browser.evaluate('decodeShareDocument(encodeShareDocument(effectDocument()))'),modes);
  const stock=await browser.evaluate('kdlDocument()');
  assert(!stock.includes('window-open')&&!stock.includes('window-movement')&&!stock.includes('pointer-wobble'));
  assert.equal((stock.match(/        off/g)||[]).length,2);
  await browser.evaluate(`byId('undo').click()`);
  assert.equal(await browser.evaluate('effectDocument().pointer ?? null'),null);
  await browser.evaluate(`byId('redo').click()`);
  assert.deepEqual(await browser.evaluate('effectDocument()'),modes);
  console.log('PASS installed Library UI, retained JSON and favorites, combo preview and schema2 modes');
} finally { await browser.close(); }
"""
    print(run(["node", "--input-type=module", "-e", source], root=root, env=browser_env))


def exercise(old_wheel, new_wheel, *, browser):
    source_schema = SOURCE_SCHEMAS[wheel_version(old_wheel)]
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
        assert document["schema"] == source_schema, "Source release emitted an unexpected schema"
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

        # The previous release already supported Library-owned files and history.
        # Create them using its actual CLI/HTTP APIs, not a current-format fixture.
        staged = cli(
            "profile",
            "--open-preset",
            "zipper",
            "--close-preset",
            "frost-vanish",
            "--movement-preset",
            "momentum-glide",
            "--desktop-motion",
            "gentle",
            "--name",
            "Saved Native Choice",
            json_output=True,
        )
        staged_file = root / "saved-native-choice.json"
        staged_file.write_text(json.dumps(staged, indent=2) + "\n")
        favorites = ["custom-saved-night", "frost-vanish", "zipper"]
        with studio(executable, root=root, env=env) as session:
            for saved_document in (document, staged):
                assert session.post("/store", {"document": saved_document, "expected": None})[
                    "changed"
                ]
            assert session.post("/preferences", {"favorites": favorites})["ok"]
            assert session.catalog()["preferences"]["favorites"] == favorites
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
        setup_files = snapshot_files(config, include)
        # Layer Library Apply over CLI setup, so each distinct restore must return
        # the exact preceding bytes. Neither history can stand in for the other.
        library_document = dict(document, name="Saved Library Active")
        library_document["actions"] = dict(document["actions"], open=document["actions"]["close"])
        if source_schema == 2:
            # The old package must own the meaning of Preserve and Off too.
            # Upgrade while these choices are active, then restore its snapshot.
            library_document["actions"] = {
                "open": None,
                "close": "off",
                "resize": "off",
                "movement": None,
            }
        with studio(executable, root=root, env=env) as session:
            selection = {
                "document": library_document,
                "allow_resize": source_schema == 2,
                "allow_movement": False,
            }
            review = session.post("/review", selection)
            assert session.post(
                "/apply", {"selection": selection, "expected": review["plan_sha256"]}
            )["changed"]
            listing = json.loads(session.get("/library"))
            assert listing["restore"] and listing["active"] == library_document
        assert include.read_bytes() != setup_files[include]
        # Installation must not migrate or activate settings. Compare the complete
        # disposable config/state trees to catch additions as well as lost files.
        protected = (custom, staged_file, root / "config", state)
        before = snapshot_files(*protected)
        install(new_wheel)
        assert snapshot_files(*protected) == before
        # Loading migrates the portable envelope without rewriting saved files
        # or changing action data. Installation itself remains passive.
        document = dict(document, schema=2)
        staged = dict(staged, schema=2)
        library_document = dict(library_document, schema=2)
        assert cli("inspect", "--custom", custom, json_output=True) == document
        assert cli("inspect", "--custom", staged_file, json_output=True) == staged
        assert "window-movement" not in cli("render", "--custom", staged_file)
        with studio(executable, root=root, env=env, current=True) as session:
            listing = json.loads(session.get("/library"))
            assert listing["active"] == library_document and listing["restore"]
            assert listing["managed"]["custom-saved-night"]["document"] == document
            assert listing["managed"]["custom-saved-native-choice"]["document"] == staged
            # An upgrade must retain conflict protection as well as a happy-path
            # Restore. Refusal must leave the user's edit and snapshot usable.
            applied_include = include.read_bytes()
            include.write_bytes(applied_include + b"// External edit after upgrade\n")
            conflict_files = snapshot_files(*protected)
            session.rejected("/restore", {}, "File changed since the plan/snapshot")
            assert snapshot_files(*protected) == conflict_files
            include.write_bytes(applied_include)
            assert not session.post("/restore", {})["dry_run"]
            assert snapshot_files(config, include) == setup_files
            assert not json.loads(session.get("/library"))["restore"]
        applied_include = include.read_bytes()
        include.write_bytes(applied_include + b"// External edit before CLI Restore\n")
        conflict_files = snapshot_files(*protected)
        try:
            cli("restore", "--transaction", old_setup["transaction"], "--apply", json_output=True)
        except subprocess.CalledProcessError as error:
            assert error.returncode == 2 and "File changed since the plan/snapshot" in error.stderr
        else:
            raise AssertionError("CLI Restore overwrote an external edit after upgrade")
        assert snapshot_files(*protected) == conflict_files
        include.write_bytes(applied_include)
        cli("restore", "--transaction", old_setup["transaction"], "--apply", json_output=True)
        assert config.read_text() == BASE and not include.exists()
        assert registry.read_bytes() == before[registry]

        with studio(executable, root=root, env=env, current=True) as session:
            assert session.catalog()["preferences"]["favorites"] == favorites
            listing = json.loads(session.get("/library"))
            assert listing["managed"]["custom-saved-night"]["document"] == document
            assert not listing["restore"] and config.read_text() == BASE
            if browser:
                before_browser = snapshot_files(*protected)
                browser_check(session, root=root, env=env)
                after_browser = snapshot_files(*protected)
                assert after_browser == before_browser, [
                    str(path.relative_to(root))
                    for path in before_browser.keys() | after_browser.keys()
                    if before_browser.get(path) != after_browser.get(path)
                ]
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
            # Build schema-2 choices through the installed CLI, then save and
            # activate them via its real Library API. Preserve has no shader;
            # Off is still a resize override and native Off stays stock-safe.
            for label, choices in (
                ("All Preserve", ("preserve",) * 4),
                ("All Off", ("off",) * 4),
                ("Mixed Modes", ("preserve", "zipper", "off", "off")),
            ):
                arguments = ["profile", "--name", label, "--pointer", "off"]
                for action, choice in zip(
                    ("open", "close", "resize", "movement"), choices, strict=True
                ):
                    arguments.extend(("--" + action, choice))
                modes = cli(*arguments, json_output=True)
                assert modes["schema"] == 2 and modes["pointer"]["strength"] == 0
                for action, choice in zip(
                    ("open", "close", "resize", "movement"), choices, strict=True
                ):
                    if choice == "preserve":
                        assert modes["actions"][action] is None
                    elif choice == "off":
                        assert modes["actions"][action] == "off"
                    else:
                        assert isinstance(modes["actions"][action], dict)
                modes_file = root / (label.lower().replace(" ", "-") + ".json")
                modes_file.write_text(json.dumps(modes) + "\n")
                modes_bytes = modes_file.read_bytes()
                assert cli("inspect", "--custom", modes_file, json_output=True) == modes
                stock = cli("render", "--custom", modes_file)
                assert "window-movement" not in stock and "pointer-wobble" not in stock
                assert stock.count("        off") == choices[:3].count("off")
                for action, choice in zip(("open", "close", "resize"), choices[:3], strict=True):
                    assert ("window-" + action in stock) == (choice != "preserve")
                assert session.post("/store", {"document": modes, "expected": None})["changed"]
                mode_id = "custom-" + label.lower().replace(" ", "-")
                assert json.loads(session.get("/library"))["managed"][mode_id]["document"] == modes
                selection = {
                    "document": modes,
                    "allow_resize": choices[2] != "preserve",
                    "allow_movement": False,
                    "allow_pointer": False,
                }
                if choices[2] == "off":
                    before_rejection = snapshot_files(config, include, state)
                    session.rejected(
                        "/review", dict(selection, allow_resize=False), "change resize effects"
                    )
                    assert snapshot_files(config, include, state) == before_rejection
                review = session.post("/review", selection)
                assert session.post(
                    "/apply", {"selection": selection, "expected": review["plan_sha256"]}
                )["changed"]
                run(["niri", "validate", "-c", config], root=root, env=env)
                assert json.loads(session.get("/library"))["active"] == modes
                assert include.read_text().endswith(stock + "\n")
                assert not session.post("/restore", {})["dry_run"]
                assert config.read_text() == BASE and not include.exists()
                assert modes_file.read_bytes() == modes_bytes
            # New optional metadata must survive saving while stock activation
            # omits it. Strength zero still requires an explicit native contract.
            for label, strength in (("Pointer Extension", 0.9), ("Pointer Disabled", 0)):
                native = dict(
                    staged,
                    name=label,
                    pointer={"strength": strength, "damping": 50, "frequency": 6},
                )
                native_file = root / (label.lower().replace(" ", "-") + ".json")
                native_file.write_text(json.dumps(native) + "\n")
                assert cli("inspect", "--custom", native_file, json_output=True) == native
                stock = cli("render", "--custom", native_file)
                assert "window-movement" not in stock and "pointer-wobble" not in stock
                assert session.post("/store", {"document": native, "expected": None})["changed"]
                native_id = "custom-" + label.lower().replace(" ", "-")
                assert (
                    json.loads(session.get("/library"))["managed"][native_id]["document"] == native
                )
                selection = {
                    "document": native,
                    "allow_resize": False,
                    "allow_movement": False,
                    "allow_pointer": False,
                }
                before_rejection = snapshot_files(config, include, state)
                for flag, message in (
                    ("allow_pointer", "verified running pointer contract"),
                    ("allow_movement", "verified running shader contract"),
                ):
                    session.rejected("/review", dict(selection, **{flag: True}), message)
                assert snapshot_files(config, include, state) == before_rejection
                review = session.post("/review", selection)
                assert session.post(
                    "/apply", {"selection": selection, "expected": review["plan_sha256"]}
                )["changed"]
                assert "pointer-wobble" not in include.read_text()
                assert "window-movement" not in include.read_text()
                assert json.loads(session.get("/library"))["active"] == native
                assert not session.post("/restore", {})["dry_run"]
                assert config.read_text() == BASE and not include.exists()
        assert registry.read_bytes() == before[registry]
        assert custom.read_bytes() == before[custom]
        assert staged_file.read_bytes() == before[staged_file]
        for path in (
            state / "profiles/saved-night.json",
            state / "profiles/saved-native-choice.json",
        ):
            assert path.read_bytes() == before[path]
        assert (state / "studio-preferences.json").read_bytes() == before[
            state / "studio-preferences.json"
        ]
        print(
            f"PASS {wheel_version(old_wheel)} -> {wheel_version(new_wheel)}: installed CLI/Studio, "
            "old JSON and shell registry, saved Library profiles and favorites, "
            "conflict-safe and exact CLI/Library Restore, native metadata and activation guards, "
            f"schema2 Preserve/Style/Off choices, user resize and schema{source_schema} files preserved"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-wheel", type=Path, required=True, help="Official v0.17.0, v0.18.0 or v0.19.0 wheel"
    )
    parser.add_argument("--to-wheel", type=Path, required=True, help="Newly built candidate wheel")
    parser.add_argument(
        "--checksums", type=Path, required=True, help="The source release SHA256SUMS"
    )
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
    if wheel_version(old_wheel) not in SOURCE_SCHEMAS:
        parser.error("--from-wheel must be an official 0.17.0, 0.18.0 or 0.19.0 release wheel")
    verify_checksum(old_wheel, args.checksums.resolve())
    exercise(old_wheel, new_wheel, browser=args.browser)


if __name__ == "__main__":
    main()
