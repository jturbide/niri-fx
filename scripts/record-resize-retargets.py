"""Record native orthogonal/timing-reload geometry against a verified source revision."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "resize_comparison", ROOT / "scripts/record-resize-comparison.py"
)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--baseline-revision", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/resize-retargets")
    parser.add_argument(
        "--publish", action="store_true", help="Publish checked GIFs and sanitized evidence"
    )
    args = parser.parse_args()
    comparison.DEST = args.output.resolve()
    comparison.DEST.mkdir(parents=True, exist_ok=True)
    comparison.BASELINE_LABEL = "Before timing fix"
    updated, updated_build, _ = comparison.experiment()
    before, baseline = comparison.baseline(
        args.baseline_manifest, None, updated_build, revision=args.baseline_revision
    )
    evidence = {
        "schema": 1,
        "scope": "Sequential native captures of orthogonal resize and timing reload. Passthrough shaders expose geometry; this does not prove deformation-phase, texture, close, clamp or physical-presentation continuity.",
        "baseline": baseline,
        "updated": {key: value for key, value in updated_build.items() if key != "binary"},
        "sources": comparison.source_hashes(
            "scripts/record-resize-retargets.py",
            "scripts/record-resize-comparison.py",
            "scripts/fixtures/resize.qml",
            "scripts/lib/nested.py",
            "scripts/lib/movement.py",
        ),
        "clips": [],
        "comparisons": [],
    }
    published = []
    for scenario, vertical in [
        ("orthogonal", False),
        ("orthogonal", True),
        ("timing-reload", True),
    ]:
        axis = "height" if vertical else "width"
        for version, binary in [("before", before), ("after", updated)]:
            clip = comparison.capture(binary, version, vertical, scenario=scenario)
            clip["edges"] = comparison.measure_video(
                comparison.DEST / f"{clip['case']}.mkv", vertical
            )
            edges = clip["edges"]
            if version == "after" or scenario == "orthogonal":
                assert 12 <= edges["min_gap_px"] <= edges["max_gap_px"] <= 20, edges
            else:
                assert edges["max_gap_px"] > 36 or edges["min_gap_px"] < -4, (
                    "Baseline timing discontinuity was not reproduced",
                    edges,
                )
            evidence["clips"].append(clip)
        gif, width = comparison.compose(axis, scenario=scenario)
        evidence["comparisons"].append(
            {"file": f"docs/gifs/{gif.name}", "width": width, "gif_sha256": comparison.digest(gif)}
        )
        published.append(
            {
                "name": gif.stem,
                "file": f"docs/gifs/{gif.name}",
                "title": f"{scenario.replace('-', ' ').title()} resize: {axis} comparison",
                "mode": "resize",
                "bytes": gif.stat().st_size,
                "fps": 50,
                "width": width,
                "colors": 128,
                "duration_ms": 1200,
                "backend": "pinned patched Niri nested winit; synthetic clients; sequential native captures shown side by side",
                "revision": updated_build["revision"],
                "patch_sha256": updated_build["patch_sha256"],
                "baseline": baseline,
                "sources": evidence["sources"],
                "checks": [
                    "verified executable and source identities",
                    "same window IDs and settled dimensions",
                    "decoded native edge separation",
                ],
            }
        )
    (comparison.DEST / "checks.json").write_text(json.dumps(evidence, indent=2) + "\n")
    if args.publish:
        for clip in published:
            shutil.copyfile(comparison.DEST / Path(clip["file"]).name, ROOT / clip["file"])
        comparison.save_clips(published)
        (ROOT / "docs/benchmarks/resize-retargets.json").write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
    print(json.dumps({"output": str(comparison.DEST), "comparisons": evidence["comparisons"]}))


if __name__ == "__main__":
    main()
