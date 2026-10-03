#!/usr/bin/env python3
"""Build a static, click-to-play gallery from the checked recording manifests."""

import argparse
import base64
import hashlib
import html
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from niri_fx.catalog import COLLECTIONS, PROFILES, RECOMMENDED, collection_names
from niri_fx.documents import MAX_DOCUMENT_BYTES, effect_document, load_document, parse_document
from niri_fx.effects import FAMILIES, PRESETS, Effect
from niri_fx.profiles import Profile

OUT = ROOT / "docs/gallery"
STUDIO = "https://jturbide.github.io/niri-fx/studio/"


def settings(clip, stem):
    """Offer the actual recorded settings, including independent profile actions."""
    panels = clip.get("panels") or ([clip] if "effect" in clip or "preset" in clip else [])
    variants = []
    defaults = asdict(Effect())
    for index, panel in enumerate(panels):
        identifier = stem if len(panels) == 1 else f"{stem}-{index + 1}"
        if "source" in panel:
            name, _, effect = parse_document(load_document(ROOT / panel["source"]))
        else:
            name = panel.get("label", panel.get("preset", identifier)).replace("-", " ").title()
            # Comparison captions may contain punctuation unsuitable for a preset
            # registry name. The recording ID remains a stable, portable fallback.
            name = (
                name
                if all(c.isascii() and (c.isalnum() or c in " _-") for c in name)
                else identifier
            )
            name = name[:48]
            effect = Effect(**panel["effect"]) if "effect" in panel else PRESETS[panel["preset"]]
            if "opening_effect" in panel:
                effect = Profile(Effect(**panel["opening_effect"]), effect)
        doc = effect_document(name, effect)
        parse_document(doc)

        def compact(values):
            return None if values is None else {k: v for k, v in values.items() if v != defaults[k]}

        payload = dict(doc)
        if isinstance(effect, Profile):
            payload["actions"] = {k: compact(v) for k, v in doc["actions"].items()}
        else:
            payload["effect"] = compact(doc["effect"])
        raw = json.dumps(payload, separators=(",", ":")).encode()
        assert len(raw) <= MAX_DOCUMENT_BYTES
        encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        preview_mode = "movement" if stem.startswith("native-swap") else clip.get("mode")
        preview = (
            f"&mode={preview_mode}&action={preview_mode}"
            if preview_mode in {"resize", "movement"}
            else ""
        )
        filename = f"nirifx-{identifier}.json"
        builtin = next((name for name, value in PROFILES.items() if value == effect), None)
        selection = f"--profile {builtin}" if builtin else f"--custom ./{filename}"
        command = f"python3 -m niri_fx studio {selection} --target standalone"
        variants.append(
            {
                "name": name,
                "filename": filename,
                "document": doc,
                "url": STUDIO + "#style=" + encoded + preview,
                "command": command,
            }
        )
    return variants


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries():
    clips = []
    for manifest in ("manifest", "native-manifest", "scenario-manifest"):
        for clip in json.loads((ROOT / f"docs/gifs/{manifest}.json").read_text())["clips"]:
            stem = Path(clip["file"]).stem
            title = stem.removeprefix("preset-").replace("-", " ").title()
            families = {clip["effect"].get("family", "fragments")} if "effect" in clip else set()
            for panel in clip.get("panels", []):
                families.add(panel["effect"].get("family", "fragments"))
                if "opening_effect" in panel:
                    families.add(panel["opening_effect"].get("family", "fragments"))
            kind = "shader"
            action = clip.get("mode", "workflow")
            if stem.startswith("native-"):
                kind, action = (
                    "experimental",
                    "swap" if "swap" in stem else clip.get("mode", "interruption"),
                )
            elif stem.startswith("stock-"):
                kind, action = "stock", "effect"
            elif action in {"move", "swap"}:
                kind = "concept"
            elif stem.startswith("workflow-"):
                kind = "workflow"
            starter = (
                RECOMMENDED.get(stem.removeprefix("preset-"), "")
                if stem.startswith("preset-")
                else ""
            )
            pairing = stem.startswith("profile-") and stem.removeprefix("profile-") in PROFILES
            clips.append(
                {
                    "id": stem,
                    "title": title,
                    "file": clip["file"],
                    "families": sorted(families),
                    "kind": kind,
                    "action": action,
                    "settings": settings(clip, stem),
                    "starter": starter,
                    "pairing": pairing,
                    "groups": collection_names(
                        stem.removeprefix("preset-").removeprefix("profile-")
                    ),
                }
            )
    # Fragments first, then other effect families; workflows stay discoverable.
    order = list(FAMILIES)
    return sorted(
        clips,
        key=lambda c: (
            min((order.index(f) for f in c["families"]), default=len(order)),
            not bool(c["starter"]),
            list(RECOMMENDED).index(c["id"].removeprefix("preset-"))
            if c["starter"]
            else len(RECOMMENDED),
            not c["id"].startswith("preset-"),
            c["title"],
        ),
    )


def document(clips):
    collection_options = "".join(
        f'<option value="{key}">{html.escape(value["label"])}</option>'
        for key, value in COLLECTIONS.items()
    )
    options = "".join(
        f'<option value="{name}">{spec["label"]}</option>' for name, spec in FAMILIES.items()
    )
    cards = []
    for clip in clips:
        name, title = clip["id"], html.escape(clip["title"])
        # Stable content URLs refresh regenerated GIFs/posters through browser
        # caches while unchanged examples remain cacheable across deployments.
        version = digest(ROOT / clip["file"])[:16]
        poster_url = f"posters/{name}.webp?v={version}"
        animation_url = f"../gifs/{name}.gif?v={version}"
        families = " ".join(clip["families"])
        labels = " · ".join(FAMILIES[f]["label"] for f in clip["families"]) or "Workflow"
        controls = []
        for variant in clip["settings"]:
            label = (
                f"<strong>{html.escape(variant['name'])}</strong>"
                if len(clip["settings"]) > 1
                else ""
            )
            try_label = (
                "Edit open/close style"
                if clip["kind"] in {"experimental", "concept"}
                else "Try in Studio"
            )
            controls.append(
                f'''<div class="style-links">{label}<a href="{variant["url"]}" data-studio>{try_label}</a><a href="presets/{variant["filename"]}" download="{variant["filename"]}">Download JSON</a><button type="button" data-command="{html.escape(variant["command"], quote=True)}">Copy local command</button></div>'''
            )
        collections = "starter" if clip["starter"] else "profiles" if clip["pairing"] else ""
        recommendation = (
            f'<p class="starter-note">{html.escape(clip["starter"])}</p>' if clip["starter"] else ""
        )
        groups = " ".join(clip["groups"])
        cards.append(f'''<article data-collection="{collections}" data-groups="{groups}" data-families="{families}" data-kind="{clip["kind"]}" data-action="{clip["action"]}" data-search="{title.lower()} {families} {groups}">
<img id="{name}" src="{poster_url}" data-poster="{poster_url}" data-animation="{animation_url}" alt="{title}" loading="lazy" width="400" height="280">
<div class="card-body"><h2>{title}</h2>{recommendation}<p>{html.escape(labels)} · {clip["kind"]}</p>
<button type="button" data-play="{name}" aria-controls="{name}" aria-pressed="false">Play</button> <a href="{animation_url}">Open GIF</a> <a href="#{name}" aria-label="Link to {title}">Link</a>{"".join(controls)}</div></article>''')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Explore NiriFX window animations: fragments, slices, wobble, hexagons, ink, pixels and more. Search the gallery and play one example at a time.">
<title>NiriFX · Effect gallery</title><link rel="stylesheet" href="gallery.css"><script src="gallery.js" defer></script></head>
<body><header><a class="brand" href="https://github.com/jturbide/niri-fx">NiriFX</a><nav><a href="{STUDIO}">Open Studio</a> · <a href="#use-on-niri">Use on Niri</a></nav></header>
<main><p class="eyebrow">WINDOWS IN MOTION</p><h1>Find your next effect.</h1><p class="intro">Preview a finished look, then use it on Niri.</p>
<p class="legend">Stock Niri open/close. Resize is opt-in; movement needs the experimental build.</p>
<div class="collections" role="group" aria-label="Browse collections"><button type="button" data-collection="starter">Start here ({len(RECOMMENDED)})</button><button type="button" data-collection="profiles">Open/close pairings ({len(PROFILES)})</button><button type="button" data-collection="all">All {len(clips)} examples</button></div>
<form role="search" onsubmit="return false"><label>Search<input type="search" id="search" placeholder="Try explosion, resize, ink…"></label>
<label>Collection<select id="collection"><option value="starter">Start here</option><option value="profiles">Open/close pairings</option><option value="all">All examples</option>{collection_options}</select></label>
<details class="filters"><summary>Filter by family, scenario or renderer</summary><div class="filter-options"><label>Family<select id="family"><option value="">All families</option>{options}</select></label>
<label>Scenario<select id="action"><option value="">All scenarios</option><option value="effect">Open / close</option><option value="resize">Resize</option><option value="swap">Swap</option><option value="movement">Native movement</option><option value="interruption">Interruption</option><option value="workflow">Workflow</option><option value="move">Move concept</option></select></label>
<label>Renderer<select id="kind"><option value="">All renderers</option><option value="shader">Studio shader</option><option value="stock">Stock Niri</option><option value="experimental">Experimental Niri</option><option value="workflow">Workflow</option><option value="concept">Concept</option></select></label></div></details></form>
<p id="count" role="status" aria-live="polite">{len(clips)} examples</p><button id="pause-all" type="button" hidden>Pause playback</button> <button id="share-view" type="button">Share this view</button>
<div id="copy-result" hidden><label id="copy-label" for="copy-text">Copy</label><input id="copy-text" readonly><p id="copy-note" role="status"></p></div>
<section id="gallery" aria-label="Animation examples">{"".join(cards)}</section><p id="empty" hidden>No examples match. <button type="button" data-collection="all">Show all examples</button></p>
<p class="legend">Shader previews use synthetic content in Studio. Stock clips run in Niri; experimental clips require the patched compositor. Concepts are simulations.</p>
<section id="use-on-niri" class="getting-started" aria-labelledby="use-heading"><h2 id="use-heading">Found a look you like?</h2>
<p>Previewing does not change your desktop. Opening, closing and optional resize work on stock Niri. Choose the setup you already use:</p>
<div class="setup-links"><a href="https://github.com/jturbide/niri-fx/blob/main/docs/standalone.md">Plain Niri or Waybar</a><a href="https://github.com/jturbide/niri-fx/blob/main/docs/getting-started.md#inir-and-iris">iNiR / iRiS</a><a href="https://github.com/jturbide/niri-fx/blob/main/docs/dms.md">DankMaterialShell</a><a href="https://github.com/jturbide/niri-fx/blob/main/docs/noctalia.md">Noctalia</a></div>
<p>For a simple first try, <a href="https://github.com/jturbide/niri-fx#quick-start">get NiriFX</a> and run <code>niri-fx</code>. Choose the same preset name in the terminal guide, review the files, then apply. Run it again and choose Undo to restore your previous settings. A shell picker can manage selection instead. Quickshell is optional.</p>
<p>For a customized look, download its JSON and use <strong>Copy local command</strong> to open it in local Studio. <a href="https://github.com/jturbide/niri-fx/blob/main/docs/web-studio.md#use-the-result-locally">Follow the download-to-desktop guide.</a></p>
<p>Made your own? <a href="https://github.com/jturbide/niri-fx/issues/new?template=share_style.yml">Share a style</a> or <a href="https://github.com/jturbide/niri-fx/issues/new?template=compatibility_report.yml">report your setup</a> to help improve NiriFX.</p></section>
<noscript>Use Open GIF to view an animation. Search and in-page playback require JavaScript.</noscript></main>
<footer>Original NiriFX effects and sample artwork · <a href="https://github.com/jturbide/niri-fx">Source and documentation</a></footer></body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated HTML and poster hashes without image dependencies",
    )
    args = parser.parse_args()
    clips = entries()
    expected = document(clips)
    index, metadata = OUT / "index.html", OUT / "posters.json"
    previous = json.loads(metadata.read_text()) if metadata.exists() else {}
    documents = {
        v["filename"]: json.dumps(v["document"], indent=2) + "\n"
        for c in clips
        for v in c["settings"]
    }
    if args.check:
        assert index.read_text() == expected, (
            "Gallery catalog changed; run scripts/build-gallery.py"
        )
        assert set(previous) == {clip["id"] for clip in clips}, "Gallery poster list is stale"
        for clip in clips:
            values = previous[clip["id"]]
            assert values == {
                "source": digest(ROOT / clip["file"]),
                "poster": digest(OUT / "posters" / (clip["id"] + ".webp")),
            }, f"Stale gallery poster: {clip['id']}"
        assert {p.name for p in (OUT / "presets").glob("*.json")} == set(documents), (
            "Gallery downloads are stale"
        )
        for filename, source in documents.items():
            assert (OUT / "presets" / filename).read_text() == source, (
                f"Stale gallery download: {filename}"
            )
    else:
        from PIL import Image

        (OUT / "posters").mkdir(parents=True, exist_ok=True)
        current = {}
        for clip in clips:
            source, poster = ROOT / clip["file"], OUT / "posters" / (clip["id"] + ".webp")
            checksum = digest(source)
            if previous.get(clip["id"], {}).get("source") != checksum or not poster.exists():
                with Image.open(source) as animation:
                    animation.seek(int(animation.n_frames * 0.18))
                    frame = animation.convert("RGB")
                    frame.thumbnail((400, 280))
                    frame.save(poster, quality=78, method=6)
            current[clip["id"]] = {"source": checksum, "poster": digest(poster)}
        index.write_text(expected)
        metadata.write_text(json.dumps(current, indent=2) + "\n")
        (OUT / "presets").mkdir(exist_ok=True)
        for filename, source in documents.items():
            (OUT / "presets" / filename).write_text(source)
    print(
        f"Checked {len(clips)} click-to-play examples"
        if args.check
        else f"Built {len(clips)} examples: docs/gallery/index.html"
    )


if __name__ == "__main__":
    main()
