"""Local library and reviewed activation, shared by the Library and Studio views.

Browser requests contain portable documents only. Config paths and compositor
executables are selected at launch, and activation uses the existing transaction
backend. iNiR remains the owner of its animation block: its own helper assembles
the replacement without writing, then NiriFX snapshots and validates the change.
"""

import contextlib
import importlib.util
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace

from .branding import APP_ID
from .documents import effect_document, load_document, parse_document
from .effects import render_kdl
from .integration import default_registry, make_custom_preset, merge_registry, read_shell_presets
from .profiles import Profile
from .setup import BEGIN, OWNED, apply_plan, change, default_config, plan_setup, restore, summarize
from .storage import atomic_write, digest, read_bytes


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
    if target == "auto":
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
        if self.folder.exists():
            for path in sorted(self.folder.glob("*.json")):
                if path.is_symlink():
                    continue
                document = load_document(path)
                customs["custom-" + parse_document(document)[1]] = document
        try:
            history = restore(self.state, self.transaction())
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
        }

    def store(self, document):
        name, slug, effect = parse_document(document)
        path = self.folder / f"{slug}.json"
        if path.is_symlink():
            raise ValueError("A saved profile cannot be a symlink")
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(path, (json.dumps(effect_document(name, effect), indent=2) + "\n").encode())
        return {"name": name, "changed": True}

    def plan(self, request):
        if not isinstance(request, dict) or set(request) != {
            "document",
            "allow_resize",
            "allow_movement",
        }:
            raise ValueError("Review requires a document and explicit action consent")
        if any(type(request[key]) is not bool for key in ("allow_resize", "allow_movement")):
            raise ValueError("Action consent must be boolean")
        name, _, effect = parse_document(request["document"])
        resize = effect.resize
        movement = effect.movement if isinstance(effect, Profile) else None
        if resize and not request["allow_resize"]:
            raise ValueError("Allow this profile to change resize effects before applying")
        if request["allow_movement"] and not movement:
            raise ValueError("This profile has no movement effect")
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
        spec.loader.exec_module(module)
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
            "movement": None,
            "validation_config": str(self.config),
            "changes": [item for item in observed if item["before"] != item["after"]],
            "observed": observed,
            "notes": [
                "Apply updates the iRiS animation block and its recognized active profile.",
                "Resize changes only when explicitly included and allowed.",
            ]
            + (["Movement is kept in the profile but not activated by iRiS."] if movement else []),
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
            "movement": None,
            "validation_config": str(self.config),
            "observed": observed,
            "changes": [item for item in observed if item["before"] != item["after"]],
            "notes": [
                "Apply selects a file in the connected Noctalia preset folder.",
                "The picker reads the active filename when opened; off and slowdown are preserved.",
            ],
        }

    def review(self, request):
        return summarize(self.plan(request))

    def apply(self, request):
        if (
            not isinstance(request, dict)
            or set(request) != {"selection", "expected"}
            or not isinstance(request["expected"], str)
        ):
            raise ValueError("Apply requires the exact reviewed selection")
        plan = self.plan(request["selection"])
        plan["selection_document"] = request["selection"]["document"]
        plan["library_scope"] = self.scope()
        return apply_plan(plan, self.state, expected=request["expected"])

    def undo(self):
        return restore(self.state, self.transaction(), apply=True)
