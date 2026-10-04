#!/usr/bin/env python3
"""Check local documentation links, release versions and recorded GIF metadata."""

import hashlib
import json
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def without_fences(text):
    return re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.M | re.S)


def anchors(text):
    seen = {}
    result = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", without_fences(text), re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def recording_sources(clip, errors):
    """Invalidate native clips when their fixture or compositor changes."""
    name = clip["file"]
    for source, digest in clip.get("sources", {}).items():
        path = ROOT / source
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f"Recording source changed; regenerate {name}: {source}")
    if "patch_sha256" in clip:
        digest = hashlib.sha256(
            (ROOT / "experimental/niri-movement.patch").read_bytes()
        ).hexdigest()
        if digest != clip["patch_sha256"]:
            errors.append(f"Native patch changed; regenerate {name}")


def main():
    errors = []
    docs = sorted(
        set(ROOT.glob("*.md"))
        | set((ROOT / "docs").rglob("*.md"))
        | set((ROOT / "examples").rglob("*.md"))
        | set((ROOT / "experimental").glob("*.md"))
        | set((ROOT / ".github").rglob("*.md"))
    )
    links = 0
    referenced_gifs = set()
    for doc in docs:
        text = without_fences(doc.read_text())
        targets = re.findall(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", text)
        targets += re.findall(r"(?:src|href)=[\"']([^\"']+)[\"']", text)
        for target in targets:
            url = urlsplit(target.strip("<>"))
            if url.scheme or url.netloc:
                continue
            links += 1
            dest = (doc.parent / unquote(url.path)).resolve() if url.path else doc
            if dest.suffix == ".gif" and dest.is_relative_to(ROOT):
                referenced_gifs.add(str(dest.relative_to(ROOT)))
            if not dest.is_relative_to(ROOT) or not dest.exists():
                errors.append(f"{doc.relative_to(ROOT)}: missing/outside local target {target}")
            elif (
                url.fragment
                and dest.suffix == ".md"
                and unquote(url.fragment) not in anchors(dest.read_text())
            ):
                errors.append(f"{doc.relative_to(ROOT)}: missing heading {target}")

    from niri_fx import __version__

    package_version = re.search(
        r'^version = "([^"]+)"$', (ROOT / "pyproject.toml").read_text(), re.M
    )
    if not package_version or package_version[1] != __version__:
        errors.append("Package and runtime versions differ")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    if not re.search(r"^## Unreleased$", changelog, re.M):
        errors.append("Changelog needs an Unreleased section")
    if not re.search(rf"^## {re.escape(__version__)} — \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M):
        errors.append(f"Changelog needs a dated entry for {__version__}")

    manifest = json.loads((ROOT / "docs/gifs/manifest.json").read_text())
    from niri_fx.catalog import PROFILES
    from niri_fx.cli import parser, selected_effect
    from niri_fx.documents import load_document, parse_document
    from niri_fx.effects import FAMILIES, PRESETS, Effect
    from niri_fx.profiles import Profile

    readme = (ROOT / "README.md").read_text()
    for summary in (
        f"**{len(PRESETS)} presets**",
        f"**{len(FAMILIES)} effect families**",
        f"**{len(PROFILES)} ready-made profiles**",
    ):
        if summary not in readme:
            errors.append(f"README catalog summary is stale; expected {summary}")

    visual_catalog = without_fences((ROOT / "docs/catalog.md").read_text())
    for prefix, styles in (("preset", PRESETS), ("profile", PROFILES)):
        for name in styles:
            if f"](gifs/{prefix}-{name}.gif)" not in visual_catalog:
                errors.append(f"Visual catalog needs its preview: {prefix}-{name}")

    examples = {}
    profile_sources = set()
    for source in sorted((ROOT / "examples").rglob("*.json")):
        try:
            document = parse_document(load_document(source))[2]
        except ValueError as error:
            errors.append(f"Invalid example {source.relative_to(ROOT)}: {error}")
            continue
        if source.stem in examples:
            errors.append(f"Example names must be unique: {source.stem}")
        examples[source.stem] = asdict(document)
        if isinstance(document, Profile):
            profile_sources.add(str(source.relative_to(ROOT)))
        if source.stem in PRESETS and examples[source.stem] != asdict(PRESETS[source.stem]):
            errors.append(f"Built-in example differs from its preset: {source.stem}")
    for name, profile in PROFILES.items():
        if examples.get(name) != asdict(profile):
            errors.append(f"Built-in profile needs its matching example: {name}")
        if not any(clip["file"] == f"docs/gifs/profile-{name}.gif" for clip in manifest["clips"]):
            errors.append(f"Built-in profile needs a dedicated recording: {name}")
    commands = "\n".join(doc.read_text() for doc in (ROOT / "examples").rglob("*.md"))
    commands = commands.replace("\\\n", "")
    checked_examples = set()
    for command in re.findall(r"^python3 -m niri_fx preview .+$", commands, re.M):
        args = parser().parse_args(shlex.split(command)[3:])
        if args.custom:
            args.custom = ROOT / args.custom
        name = args.output.stem
        if name not in examples or asdict(selected_effect(args)) != examples[name]:
            errors.append(f"Example preview command differs from saved JSON: {name}")
        checked_examples.add(name)
    if checked_examples != set(examples):
        errors.append("Every example needs a matching documented preview command")
    recorded = {clip["file"]: clip for clip in manifest["clips"]}
    if len(recorded) != len(manifest["clips"]):
        errors.append("GIF manifest has duplicate file entries")
    # Coverage is an obligation of adding a preset, not just a check that the
    # remaining old recordings still match. Profiles also need an importable demo.
    for preset in PRESETS:
        path = f"docs/gifs/preset-{preset}.gif"
        clip = recorded.get(path, {})
        if clip.get("preset") != preset:
            errors.append(f"Preset needs a dedicated recording: {preset}")
        elif "effect" not in clip:
            errors.append(f"Preset recording needs exact parameter metadata: {preset}")
    showcases = json.loads((ROOT / "docs/gifs/showcases.json").read_text())["clips"]
    showcased_sources = set()
    for spec in showcases:
        expected = []
        for panel in spec["panels"]:
            if "source" in panel:
                showcased_sources.add(panel["source"])
                document = parse_document(load_document(ROOT / panel["source"]))[2]
                effect = (
                    (
                        getattr(document, spec["mode"])
                        if spec["mode"] in {"resize", "movement"}
                        else document.close
                    )
                    if isinstance(document, Profile)
                    else document
                )
                origin = {"source": panel["source"]}
                if isinstance(document, Profile) and spec["mode"] == "effect":
                    origin["opening_effect"] = asdict(document.open)
            else:
                effect = replace(PRESETS[panel["preset"]], **panel["overrides"])
                origin = {"preset": panel["preset"]}
            expected.append({"effect": asdict(effect), **origin, "label": panel["label"]})
        actual = recorded.get(f"docs/gifs/{spec['name']}.gif", {}).get("panels")
        if actual is not None:
            actual = [
                {
                    **panel,
                    "effect": asdict(Effect(**panel["effect"])),
                    **(
                        {"opening_effect": asdict(Effect(**panel["opening_effect"]))}
                        if "opening_effect" in panel
                        else {}
                    ),
                }
                for panel in actual
            ]
        if actual != expected:
            errors.append(f"Showcase settings changed; regenerate {spec['name']}.gif")
    # Native overlap recordings carry a complete profile and its source hash.
    # Their combined compositor behavior cannot be faithfully shown by a single
    # canvas action; count these checked native clips as profile showcases.
    for clip in json.loads((ROOT / "docs/gifs/scenario-manifest.json").read_text())["clips"]:
        if clip.get("source") in profile_sources and clip["source"] in clip.get("sources", {}):
            showcased_sources.add(clip["source"])
    for source in sorted(profile_sources - showcased_sources):
        errors.append(f"Profile example needs a showcase: {source}")
    for clip in manifest["clips"]:
        if (
            "preset" in clip
            and "effect" in clip
            and asdict(Effect(**clip["effect"])) != asdict(PRESETS[clip["preset"]])
        ):
            errors.append(f"Preset recording settings changed: {clip['preset']}")
        dest = ROOT / clip["file"]
        if not dest.exists() or dest.stat().st_size != clip["bytes"]:
            errors.append(f"GIF manifest size differs: {clip['file']}")
    native = json.loads((ROOT / "docs/gifs/native-manifest.json").read_text())["clips"]
    for clip in native:
        dest = ROOT / clip["file"]
        if not dest.exists() or dest.stat().st_size != clip["bytes"]:
            errors.append(f"Native GIF manifest size differs: {clip['file']}")
        if asdict(Effect(**clip["effect"])) != asdict(PRESETS[clip["preset"]]):
            errors.append(f"Native preset settings changed: {clip['preset']}")
        recording_sources(clip, errors)
    scenarios = json.loads((ROOT / "docs/gifs/scenario-manifest.json").read_text())["clips"]
    if len({clip["name"] for clip in scenarios}) != len(scenarios):
        errors.append("Scenario manifest has duplicate names")
    for clip in scenarios:
        dest = ROOT / clip["file"]
        if clip["file"] != f"docs/gifs/{clip['name']}.gif":
            errors.append(f"Scenario file/name mismatch: {clip['name']}")
        if not dest.is_file() or dest.stat().st_size != clip["bytes"]:
            errors.append(f"Scenario GIF manifest size differs: {clip['file']}")
        if not clip.get("backend") or not clip.get("checks"):
            errors.append(f"Scenario needs renderer and acceptance metadata: {clip['name']}")
        if "preset" in clip:
            expected = replace(PRESETS[clip["preset"]], **clip.get("overrides", {}))
            if asdict(Effect(**clip["effect"])) != asdict(expected):
                errors.append(f"Scenario settings changed; regenerate {clip['name']}.gif")
        recording_sources(clip, errors)
    gifs = list((ROOT / "docs/gifs").glob("*.gif"))
    listed = {clip["file"] for clip in manifest["clips"]} | {"docs/gifs/native-swap.gif"}
    listed |= {clip["file"] for clip in native}
    listed |= {clip["file"] for clip in scenarios}
    if {str(gif.relative_to(ROOT)) for gif in gifs} != listed:
        errors.append("GIF files and manifest differ (native swap is recorded separately)")
    # Current catalog summaries must track the actual media, while historical
    # release entries retain their original counts.
    for relative in ("docs/showcases.md", "docs/gifs/README.md", "docs/validation.md"):
        summary = (ROOT / relative).read_text()
        for label, pattern, expected in (
            ("GIF", r"\*\*(\d+) GIFs\*\*", len(gifs)),
            ("preset", r"\*\*(\d+) (?:built-in )?presets\*\*", len(PRESETS)),
        ):
            count = re.search(pattern, summary)
            if not count or int(count[1]) != expected:
                errors.append(f"{relative}: current {label} count must be {expected}")
    for path in sorted(listed - referenced_gifs):
        errors.append(f"GIF needs a documentation link: {path}")
    for gif in gifs:
        with gif.open("rb") as stream:
            if stream.read(6) not in (b"GIF87a", b"GIF89a"):
                errors.append(f"Invalid GIF header: {gif.relative_to(ROOT)}")
    gallery = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build-gallery.py"), "--check"],
        capture_output=True,
        text=True,
    )
    if gallery.returncode:
        errors.append("Gallery is stale or invalid: " + gallery.stderr.strip())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Checked {len(docs)} documents, {links} local links, {len(gifs)} GIFs and version {__version__}"
    )
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
