"""Local library and reviewed activation, shared by the Library and Studio views.

Browser requests contain portable documents only. Config paths and compositor
executables are selected at launch, and activation uses the existing transaction
backend. iNiR remains the owner of its animation block: its own helper assembles
the replacement without writing, then NiriFX snapshots and validates the change.
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

from .branding import APP_ID
from .documents import MAX_DOCUMENT_BYTES, effect_document, load_document, parse_document
from .effects import render_kdl
from .integration import default_registry, make_custom_preset, merge_registry, read_shell_presets
from .profiles import Profile
from .setup import BEGIN, OWNED, apply_plan, change, default_config, plan_setup, restore, summarize
from .storage import atomic_write, digest, read_bytes

MAX_PROFILES = 100


def registry_document(preset):
    if preset.get("generator") != APP_ID:
        return None
    name = preset.get("name", "").removeprefix("NiriFX · ")
    if "profile" in preset:
        document = dict(preset["profile"], name=name)
    else:
        document = {"schema": 3, "name": name, "effect": preset.get("effect")}
    _, _, effect = parse_document(document)
    return effect_document(name, effect)


def studio_target(arguments):
    target = getattr(arguments, "target", "auto")
    if target != "native" and any(
        getattr(arguments, key, None) is not None for key in ("native_root", "native_base")
    ):
        raise ValueError("--native-root and --native-base require --target native")
    if target == "auto":
        from . import native_session

        # A verified managed compositor owns its effects independently of the
        # surrounding shell. Merely having a retained bundle is not enough.
        socket_path = os.environ.get("NIRI_SOCKET")
        if socket_path:
            try:
                report = native_session.status(
                    native_session.default_root(), socket_path=socket_path
                )
                if report["running"]["status"] == "matched":
                    return "native"
            except (OSError, ValueError):
                pass
        return (
            "inir"
            if (Path(arguments.inir_root) / "scripts/niri-config.py").is_file()
            else "standalone"
        )
    return target


class Library:
    def __init__(self, arguments, target):
        self.arguments = arguments
        self.target = target
        self.config = Path(getattr(arguments, "config", default_config())).expanduser()
        self.state = Path(arguments.state).expanduser() / "studio-apply"
        self.folder = Path(arguments.state).expanduser() / "profiles"
        if target == "native":
            from . import native_session

            root = getattr(arguments, "native_root", None)
            if root is None:
                root = native_session.default_root()
            self.native_root = Path(root).expanduser().absolute()
            base = getattr(arguments, "native_base", None)
            if base is None:
                base = native_session.load_selection(self.native_root)["selected"]
            if base is None:
                raise ValueError("Select a managed bundle first or supply --native-base")
            # A Studio session always derives from the same launch-time bundle.
            # Changes to the selector invalidate review without silently rebasing edits.
            self.native_base = native_session.inspect_bundle(self.native_root, base)
            self.native_socket = os.environ.get("NIRI_SOCKET")

    def scope(self):
        """Bind history to the launch configuration, including the picker connection."""
        scope = {"target": self.target, "config": str(self.config.expanduser().resolve())}
        if self.target == "noctalia":
            for key in ("preset_dir", "picker_file"):
                value = getattr(self.arguments, key, None)
                scope[key] = str(Path(value).expanduser().resolve()) if value else None
        return scope

    def transaction(self):
        for path in sorted(self.state.glob("*/manifest.json"), reverse=True):
            data = json.loads(path.read_text())
            if data.get("status") == "applied" and data.get("library_scope") == self.scope():
                return data["id"]
        raise ValueError("No applied NiriFX Library snapshot remains for this setup")

    def listing(self):
        if self.target == "native":
            return self.native_listing()
        customs = {}
        active = None
        active_name = "Current Niri settings"
        if self.target == "inir":
            shell = read_shell_presets(self.arguments.inir_root)
            for preset in shell["presets"]:
                try:
                    document = registry_document(preset)
                    if document and preset["id"].startswith("niri-fx-custom-"):
                        customs["custom-" + parse_document(document)[1]] = document
                    if preset["id"] == shell.get("active"):
                        active, active_name = document, preset["name"]
                except (ValueError, KeyError):
                    continue  # A foreign or obsolete entry is not an editable document.
        managed, warnings = self.saved_profiles()
        customs.update({key: entry["document"] for key, entry in managed.items()})
        try:
            history = restore(
                self.state,
                self.transaction(),
                binary=getattr(self.arguments, "movement_binary", None),
                verify_native=False,
            )
        except ValueError:
            history = None
        if history and self.target != "inir":
            manifest = json.loads(
                (self.state / history["transaction"] / "manifest.json").read_text()
            )
            if manifest.get("selection_document"):
                name, _, effect = parse_document(manifest["selection_document"])
                active = effect_document(name, effect)
                active_name = name
        return {
            "customs": customs,
            "active": active,
            "active_name": active_name,
            "restore": history is not None,
            "target": self.target,
            "managed": managed,
            "warnings": warnings,
        }

    def saved_profiles(self):
        """Skip damaged files individually; never repair or delete them while browsing."""
        managed, skipped = {}, 0
        self.check_folder()
        for path in sorted(self.folder.glob("*.json")):
            try:
                if path.is_symlink():
                    raise ValueError("Profile symlink")
                with path.open("rb") as stream:
                    raw = stream.read(MAX_DOCUMENT_BYTES + 1)
                if len(raw) > MAX_DOCUMENT_BYTES:
                    raise ValueError("Profile exceeds 16 KiB")
                document = json.loads(raw)
                name, slug, effect = parse_document(document)
                if path.stem != slug:
                    raise ValueError("Profile filename does not match its name")
                managed["custom-" + slug] = {
                    "document": effect_document(name, effect),
                    "expected": digest(raw),
                }
            except (OSError, ValueError):
                skipped += 1
        warnings = (
            [f"{skipped} saved profile file(s) could not be read. Their files were left untouched."]
            if skipped
            else []
        )
        return managed, warnings

    def native_listing(self):
        """Separate retained configuration from the advertised running renderer."""
        from . import native_live, native_session

        report = native_session.status(self.native_root, socket_path=self.native_socket)
        managed, warnings = self.saved_profiles()
        base_recipe = self.native_base.get("customization")
        baseline = base_recipe["baseline_bundle"] if base_recipe else self.native_base["bundle_id"]
        selected = report["selection"]["selected"]
        active, recipe, reopen = None, None, False
        for row in report["bundles"]:
            if row["bundle_id"] == selected:
                if row["status"] == "metadata-match":
                    recipe = row.get("customization")
                    if recipe:
                        active = recipe["document"]
                        reopen = recipe["baseline_bundle"] == baseline
                else:
                    warnings.append("The next-login bundle is unavailable: " + row["reason"])
        previous = report["selection"].get("previous")
        rollback_available = "previous" in report["selection"] and (
            previous is None
            or any(
                row["bundle_id"] == previous and row["status"] == "metadata-match"
                for row in report["bundles"]
            )
        )
        return {
            "customs": {key: entry["document"] for key, entry in managed.items()},
            "managed": managed,
            "warnings": warnings,
            "active": active,
            "active_name": active["name"] if active else (selected or "Stock Niri"),
            "restore": rollback_available,
            "target": self.target,
            "native": {
                "base_bundle": self.native_base["bundle_id"],
                "baseline_bundle": baseline,
                "selection": report["selection"],
                "running": report["running"],
                "bundles": report["bundles"],
                "recipe": recipe,
                "reopen": reopen,
                "live": native_live.context(
                    self.native_root,
                    self.native_base["bundle_id"],
                    socket_path=self.native_socket,
                ),
            },
        }

    def check_folder(self):
        if self.folder.is_symlink():
            raise ValueError("The saved profiles folder cannot be a symlink")

    @contextlib.contextmanager
    def profile_lock(self):
        """Serialize cooperating Studio sessions; fingerprints also catch outside edits."""
        self.check_folder()
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.folder / ".lock"
        if lock_path.is_symlink():
            raise ValueError("The saved profiles lock cannot be a symlink")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    @staticmethod
    def check_expected(path, expected):
        if expected is not None and (
            not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected)
        ):
            raise ValueError("Expected profile fingerprint must be a SHA-256 value or null")
        if path.is_symlink():
            raise ValueError("A saved profile cannot be a symlink")
        if digest(read_bytes(path)) != expected:
            raise ValueError("Saved profile changed. Refresh My profiles before trying again.")

    def store(self, request):
        if not isinstance(request, dict) or set(request) != {"document", "expected"}:
            raise ValueError("Save requires a document and its expected profile fingerprint")
        document, expected = request["document"], request["expected"]
        name, slug, effect = parse_document(document)
        path = self.folder / f"{slug}.json"
        with self.profile_lock():
            self.check_expected(path, expected)
            if expected is None and len(list(self.folder.glob("*.json"))) >= MAX_PROFILES:
                raise ValueError("My profiles is full. Remove a profile or export JSON.")
            atomic_write(
                path, (json.dumps(effect_document(name, effect), indent=2) + "\n").encode()
            )
        return {"name": name, "changed": True}

    def manage(self, request):
        """Rename/remove Library-owned JSON only. Shell registries and live settings stay separate."""
        if not isinstance(request, dict) or request.get("action") not in ("rename", "remove"):
            raise ValueError("Choose rename or remove for a saved Library profile")
        action = request["action"]
        keys = {"action", "id", "expected"} | ({"name"} if action == "rename" else set())
        if (
            set(request) != keys
            or not isinstance(request["id"], str)
            or not re.fullmatch(r"custom-[a-z0-9][a-z0-9-]{0,47}", request["id"])
        ):
            raise ValueError("Profile management accepts a saved profile ID, never a path")
        path = self.folder / f"{request['id'].removeprefix('custom-')}.json"
        if request["expected"] is None:
            raise ValueError("Select an existing Library profile first")
        with self.profile_lock():
            self.check_expected(path, request["expected"])
            document = load_document(path)
            name, slug, effect = parse_document(document)
            if path.stem != slug:
                raise ValueError("Profile filename does not match its name")
            if action == "remove":
                path.unlink()
            else:
                updated = dict(document, name=request["name"])
                name, slug, effect = parse_document(updated)
                destination = self.folder / f"{slug}.json"
                if destination != path and (destination.exists() or destination.is_symlink()):
                    raise ValueError(
                        "That name already belongs to a saved profile. Choose another."
                    )
                atomic_write(
                    destination,
                    (json.dumps(effect_document(name, effect), indent=2) + "\n").encode(),
                )
                if destination != path:
                    try:
                        self.check_expected(path, request["expected"])
                        path.unlink()
                    except (OSError, ValueError):
                        destination.unlink()
                        raise
        return {"name": name, "changed": True}

    def plan(self, request):
        if self.target == "native":
            from .native_customization import configure_plan

            if (
                not isinstance(request, dict)
                or "document" not in request
                or set(request) - {"document", "fragment_preset"}
            ):
                raise ValueError(
                    "Managed review accepts a document and optional fragment preset only"
                )
            plan = configure_plan(
                self.native_root,
                self.native_base["bundle_id"],
                request["document"],
                fragment_preset=request.get("fragment_preset"),
            )
            return self.native_activation_plan(plan, self.native_base["bundle_id"])
        required = {"document", "allow_resize", "allow_movement"}
        if (
            not isinstance(request, dict)
            or not required <= set(request)
            or set(request) - required - {"allow_pointer"}
        ):
            raise ValueError("Review requires a document and explicit action consent")
        if any(
            type(request[key]) is not bool
            for key in ("allow_resize", "allow_movement", "allow_pointer")
            if key in request
        ):
            raise ValueError("Action consent must be boolean")
        name, _, effect = parse_document(request["document"])
        resize = effect.resize
        movement = effect.movement if isinstance(effect, Profile) else None
        pointer = effect.pointer if isinstance(effect, Profile) else None
        allow_pointer = request.get("allow_pointer", False)
        if resize and not request["allow_resize"]:
            raise ValueError("Allow this profile to change resize effects before applying")
        if request["allow_movement"] and not movement:
            raise ValueError("This profile has no movement effect")
        if allow_pointer and pointer is None:
            raise ValueError("This profile has no pointer settings")
        if allow_pointer and self.target != "standalone":
            raise ValueError(
                "Pointer activation requires the verified standalone path; shell pickers activate stock Niri actions only"
            )
        args = SimpleNamespace(
            config=self.config,
            target=self.target,
            inir_root=self.arguments.inir_root,
            registry=self.arguments.registry,
            base=self.arguments.base,
            launcher=False,
            preset="balanced",
            profile=None,
            name=name,
            enable_movement=request["allow_movement"],
            enable_pointer=allow_pointer,
            movement_binary=getattr(self.arguments, "movement_binary", None),
        )
        document = effect_document(name, effect)
        if self.target == "standalone":
            return plan_setup(args, effect, custom=document)
        if self.target == "noctalia":
            if request["allow_movement"]:
                raise ValueError("The Noctalia preset picker activates stock Niri actions only")
            return self.file_picker_plan(document, effect)
        if self.target != "inir":
            raise ValueError("Unsupported activation target")
        if request["allow_movement"]:
            raise ValueError("The iRiS integration activates stock Niri actions only")
        if (
            self.config.resolve() != default_config().resolve()
            or Path(args.registry).resolve() != default_registry().resolve()
        ):
            raise ValueError(
                "iRiS Apply requires its own config and registry; use XDG_CONFIG_HOME for an isolated session"
            )
        if BEGIN in self.config.read_text():
            raise ValueError("Restore the standalone override before applying through iRiS")
        shell = read_shell_presets(args.inir_root)
        preset = make_custom_preset(shell, document, args.base)
        registry = Path(args.registry)
        old_registry = read_bytes(registry.resolve())
        merged = merge_registry(json.loads(old_registry) if old_registry else {}, [preset])
        helper = Path(args.inir_root) / "scripts/niri-config.py"
        spec = importlib.util.spec_from_file_location("_nirifx_inir_helper", helper)
        module = importlib.util.module_from_spec(spec)
        # Retain module metadata without reading or writing the shell checkout's
        # bytecode cache. Review must use current source and leave updates clean.
        exec(compile(helper.read_bytes(), str(helper), "exec"), module.__dict__)
        animation = module.resolve_niri_section_file("config.d/60-animations.kdl")
        before = read_bytes(animation.resolve())
        captured = []

        def capture(path, text):
            if Path(path) != animation:
                raise ValueError("iNiR changed its animation file contract")
            captured.append(text.encode())
            return 0

        # Invoke the installed serializer, retaining off/slowdown and its exact
        # preset matching. Override only I/O and registry lookup on this private
        # module instance; neither the installed source nor live config is edited.
        module._load_animation_presets = lambda: {"presets": [preset]}
        module._write_validated = capture
        with contextlib.redirect_stdout(io.StringIO()):
            result = module.cmd_apply_animation_preset([preset["id"]])
        if result != 0 or len(captured) != 1:
            raise ValueError("iNiR could not assemble the selected profile")
        observed = [
            change(
                registry,
                (json.dumps(merged, indent=2, ensure_ascii=False) + "\n").encode(),
                old_registry,
            ),
            change(animation, captured[0], before),
            change(self.config, self.config.read_bytes()),
        ]
        return {
            "target": "inir-active",
            "activation": "iRiS animation service",
            "selection": {"name": name, "helper_sha256": digest(helper.read_bytes())},
            "effect": document,
            "desktop_motion": document.get("motion"),
            "pointer": document.get("pointer"),
            "pointer_activation": None,
            "movement": None,
            "validation_config": str(self.config),
            "changes": [item for item in observed if item["before"] != item["after"]],
            "observed": observed,
            "notes": [
                "Apply updates the iRiS animation block and its recognized active profile.",
                "Resize changes only when explicitly included and allowed.",
            ]
            + (["Movement is kept in the profile but not activated by iRiS."] if movement else [])
            + (
                ["Pointer settings are kept in the profile but not activated by iRiS."]
                if pointer
                else []
            ),
        }

    def file_picker_plan(self, document, effect):
        """Update an explicitly connected Noctalia preset folder and target file.

        Preserve the plugin's off/slowdown controls. Paths come from CLI setup,
        never a web request; imported JSON cannot redirect an export or Apply.
        """
        directory = getattr(self.arguments, "preset_dir", None)
        target = getattr(self.arguments, "picker_file", None)
        if directory is None or target is None:
            raise ValueError(
                "Connect Noctalia with --preset-dir and --picker-file, or export a preset file"
            )
        directory, target = Path(directory).expanduser(), Path(target).expanduser()
        _, slug, _ = parse_document(document)
        preset = directory / f"niri-fx-custom-{slug}.kdl"
        existing = read_bytes(preset.resolve())
        if existing is not None and not existing.startswith((OWNED + "\n").encode()):
            raise ValueError("The selected preset filename already belongs to another provider")
        old_target = read_bytes(target.resolve())
        if old_target is None:
            raise ValueError(
                "Select a preset in Noctalia first to create its connected target file"
            )
        text = old_target.decode()
        includes = list(re.finditer(r'(?m)^\s*include\s+"[^"\n]+"\s*$', text))
        if len(includes) > 1 or not re.fullmatch(
            r'\s*(?://[^\n]*\n|include\s+"[^"\n]+"\s*|animations\s*\{\s*(?:off\s*|slowdown\s+[0-9.]+\s*)?\}\s*)*',
            text,
        ):
            raise ValueError("Noctalia target contains independent settings; leaving it untouched")
        include = "include " + json.dumps(str(preset.absolute()))
        if includes:
            match = includes[0]
            updated = text[: match.start()] + include + "\n" + text[match.end() :]
        else:
            updated = include + "\n" + text
        # A dedicated target must already be included directly by the config.
        # We never append a competing standalone override for a shell picker.
        root_text = self.config.read_text()
        connected = any(
            (self.config.parent / path).resolve() == target.resolve()
            for path in re.findall(r'(?m)^\s*include\s+"([^"\n]+)"', root_text)
        )
        if not connected:
            raise ValueError("The Noctalia target is not included by this Niri config")
        observed = [
            change(preset, (OWNED + "\n" + render_kdl(effect)).encode(), existing),
            change(target, updated.encode(), old_target),
            change(self.config, root_text.encode()),
        ]
        return {
            "target": "noctalia",
            "activation": "Noctalia preset file",
            "selection": document["name"],
            "effect": document,
            "desktop_motion": document.get("motion"),
            "pointer": document.get("pointer"),
            "pointer_activation": None,
            "movement": None,
            "validation_config": str(self.config),
            "observed": observed,
            "changes": [item for item in observed if item["before"] != item["after"]],
            "notes": [
                "Apply selects a file in the connected Noctalia preset folder.",
                "The picker reads the active filename when opened; off and slowdown are preserved.",
            ]
            + (
                ["Pointer settings are kept in the profile but not activated by Noctalia."]
                if document.get("pointer") is not None
                else []
            ),
        }

    def review(self, request):
        return summarize(self.plan(request))

    def native_activation_plan(self, plan, base_bundle):
        """Bind direct desktop activation to the same review as retained selection."""
        from . import native_live

        plan["activation"] = "next-login"
        if base_bundle is None:
            return plan
        live = native_live.context(self.native_root, base_bundle, socket_path=self.native_socket)
        if live["ready"]:
            plan["native_live"] = live["identity"]
            plan["activation"] = "live-and-next-login"
            plan["notes"] = [
                "Applies these effects to the verified running NiriFX session and the next login.",
                "The previous selection and all retained configurations remain available.",
                "Preserve inherits the original saved baseline, including its existing styles.",
            ]
        else:
            plan["notes"].append(live["detail"])
        return plan

    def native_activation_result(self, plan, result, base_bundle):
        from . import native_live

        result["activation"] = "next-login"
        if plan.get("native_live"):
            live = native_live.apply(
                self.native_root,
                base_bundle,
                plan["selection"]["selected"],
                socket_path=self.native_socket,
                expected_identity=plan["native_live"],
            )
            result["live"] = live
            if live["status"] == "applied":
                result["activation"] = "live-and-next-login"
        return result

    def apply(self, request):
        if (
            not isinstance(request, dict)
            or set(request) != {"selection", "expected"}
            or not isinstance(request["expected"], str)
        ):
            raise ValueError("Apply requires the exact reviewed selection")
        plan = self.plan(request["selection"])
        if self.target == "native":
            from .native_customization import apply_native

            result = apply_native(plan, self.native_root, expected=request["expected"])
            return self.native_activation_result(plan, result, self.native_base["bundle_id"])
        plan["selection_document"] = request["selection"]["document"]
        plan["library_scope"] = self.scope()
        return apply_plan(plan, self.state, expected=request["expected"])

    def undo(self):
        if self.target == "native":
            raise ValueError(
                "Managed rollback requires Review rollback, then confirm the reviewed changes"
            )
        return restore(
            self.state,
            self.transaction(),
            apply=True,
            binary=getattr(self.arguments, "movement_binary", None),
        )

    def rollback_review(self, request):
        if self.target != "native" or request != {}:
            raise ValueError("Managed rollback accepts no client-selected path or bundle")
        from .native_session import rollback_plan

        plan = rollback_plan(self.native_root)
        return summarize(self.native_activation_plan(plan, plan["selection"]["selected"]))

    def rollback_apply(self, request):
        if (
            self.target != "native"
            or not isinstance(request, dict)
            or set(request) != {"expected"}
            or not isinstance(request["expected"], str)
        ):
            raise ValueError("Managed rollback requires the exact reviewed fingerprint")
        from .native_session import rollback_plan

        plan = rollback_plan(self.native_root)
        base = plan["selection"]["selected"]
        plan = self.native_activation_plan(plan, base)
        result = apply_plan(
            plan,
            self.native_root / "state/selection",
            expected=request["expected"],
        )
        result.pop("restore", None)
        return self.native_activation_result(plan, result, base)
