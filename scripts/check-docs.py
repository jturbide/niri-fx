#!/usr/bin/env python3
"""Check local documentation links, release versions and recorded GIF metadata."""
import json
from pathlib import Path
import re
import sys
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


def main():
    errors = []
    docs = sorted(set(ROOT.glob("*.md")) | set((ROOT / "docs").rglob("*.md"))
                  | set((ROOT / "experimental").glob("*.md"))
                  | set((ROOT / ".github").rglob("*.md")))
    links = 0
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
            if not dest.is_relative_to(ROOT) or not dest.exists():
                errors.append(f"{doc.relative_to(ROOT)}: missing/outside local target {target}")
            elif url.fragment and dest.suffix == ".md" and unquote(url.fragment) not in anchors(dest.read_text()):
                errors.append(f"{doc.relative_to(ROOT)}: missing heading {target}")

    from niri_fragments import __version__
    package_version = re.search(r'^version = "([^"]+)"$', (ROOT / "pyproject.toml").read_text(), re.M)
    if not package_version or package_version[1] != __version__:
        errors.append("Package and runtime versions differ")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    if not re.search(r"^## Unreleased$", changelog, re.M):
        errors.append("Changelog needs an Unreleased section")
    if not re.search(rf"^## {re.escape(__version__)} — \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M):
        errors.append(f"Changelog needs a dated entry for {__version__}")

    manifest = json.loads((ROOT / "docs/gifs/manifest.json").read_text())
    for clip in manifest["clips"]:
        dest = ROOT / clip["file"]
        if not dest.exists() or dest.stat().st_size != clip["bytes"]:
            errors.append(f"GIF manifest size differs: {clip['file']}")
    gifs = list((ROOT / "docs/gifs").glob("*.gif"))
    listed = {clip["file"] for clip in manifest["clips"]} | {"docs/gifs/native-swap.gif"}
    if {str(gif.relative_to(ROOT)) for gif in gifs} != listed:
        errors.append("GIF files and manifest differ (native swap is recorded separately)")
    for gif in gifs:
        with gif.open("rb") as stream:
            if stream.read(6) not in (b"GIF87a", b"GIF89a"):
                errors.append(f"Invalid GIF header: {gif.relative_to(ROOT)}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Checked {len(docs)} documents, {links} local links, {len(gifs)} GIFs and version {__version__}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
