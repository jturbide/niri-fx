#!/usr/bin/env python3
"""Build a static, click-to-play gallery from the checked recording manifests."""

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from niri_fx.effects import FAMILIES

OUT = ROOT / "docs/gallery"


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
                kind, action = "experimental", "swap" if "swap" in stem else "interruption"
            elif stem.startswith("stock-"):
                kind, action = "stock", "effect"
            elif action in {"move", "swap"}:
                kind = "concept"
            elif stem.startswith("workflow-"):
                kind = "workflow"
            clips.append(
                {
                    "id": stem,
                    "title": title,
                    "file": clip["file"],
                    "families": sorted(families),
                    "kind": kind,
                    "action": action,
                }
            )
    # Fragments first, then other effect families; workflows stay discoverable.
    order = list(FAMILIES)
    return sorted(
        clips,
        key=lambda c: (
            min((order.index(f) for f in c["families"]), default=len(order)),
            not c["id"].startswith("preset-"),
            c["title"],
        ),
    )


def document(clips):
    options = "".join(
        f'<option value="{name}">{spec["label"]}</option>' for name, spec in FAMILIES.items()
    )
    cards = []
    for clip in clips:
        name, title = clip["id"], html.escape(clip["title"])
        families = " ".join(clip["families"])
        labels = " · ".join(FAMILIES[f]["label"] for f in clip["families"]) or "Workflow"
        cards.append(f'''<article data-families="{families}" data-kind="{clip["kind"]}" data-action="{clip["action"]}" data-search="{title.lower()} {families}">
<img id="{name}" src="posters/{name}.webp" data-poster="posters/{name}.webp" data-animation="../gifs/{name}.gif" alt="{title}" loading="lazy" width="400" height="280">
<div class="card-body"><h2>{title}</h2><p>{html.escape(labels)} · {clip["kind"]}</p>
<button type="button" data-play="{name}" aria-controls="{name}" aria-pressed="false">Play</button> <a href="../gifs/{name}.gif">Open GIF</a></div></article>''')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Explore NiriFX window animations: fragments, slices, wobble, hexagons, ink, pixels and more. Search the gallery and play one example at a time.">
<title>NiriFX · Effect gallery</title><link rel="stylesheet" href="gallery.css"><script src="gallery.js" defer></script></head>
<body><header><a class="brand" href="https://github.com/jturbide/niri-fx">NiriFX</a><a href="https://github.com/jturbide/niri-fx#quick-start">Get started</a></header>
<main><p class="eyebrow">WINDOWS IN MOTION</p><h1>Find your next effect.</h1><p class="intro">Fragments, ribbons, springs and quiet ripples. Search {len(clips)} examples and play one at a time. Every preview starts paused.</p>
<p class="legend">Shader previews use synthetic content in Studio. Stock clips run in Niri; experimental clips require the patched compositor. Concepts are simulations. Resize is always opt-in.</p>
<form role="search" onsubmit="return false"><label>Search<input type="search" id="search" placeholder="Try explosion, resize, ink…"></label>
<label>Family<select id="family"><option value="">All families</option>{options}</select></label>
<label>Scenario<select id="action"><option value="">All scenarios</option><option value="effect">Open / close</option><option value="resize">Resize</option><option value="swap">Swap</option><option value="interruption">Interruption</option><option value="workflow">Workflow</option><option value="move">Move concept</option></select></label>
<label>Renderer<select id="kind"><option value="">All renderers</option><option value="shader">Studio shader</option><option value="stock">Stock Niri</option><option value="experimental">Experimental Niri</option><option value="workflow">Workflow</option><option value="concept">Concept</option></select></label></form>
<p id="count" role="status" aria-live="polite">{len(clips)} examples</p><button id="pause-all" type="button">Pause playback</button>
<section id="gallery" aria-label="Animation examples">{"".join(cards)}</section><p id="empty" hidden>No examples match. Try a different search or filter.</p>
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
    print(
        f"Checked {len(clips)} click-to-play examples"
        if args.check
        else f"Built {len(clips)} examples: docs/gallery/index.html"
    )


if __name__ == "__main__":
    main()
