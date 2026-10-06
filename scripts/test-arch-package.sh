#!/usr/bin/env bash
# Build and install only inside a disposable official Arch Linux container.
set -euo pipefail

if [[ ${NIRIFX_ARCH_PACKAGE_CONTAINER:-} != 1 ]] ||
    [[ ! -f /.dockerenv && ! -f /run/.containerenv ]]; then
    printf '%s\n' 'Refusing host execution: use a disposable container with NIRIFX_ARCH_PACKAGE_CONTAINER=1.' >&2
    exit 2
fi
if [[ $# -lt 1 || $# -gt 2 || $EUID != 0 ]]; then
    printf '%s\n' 'Usage inside the container as root: test-arch-package.sh OUTPUT_DIRECTORY [niri-fx|niri-fx-git]' >&2
    exit 2
fi
package_name=${2:-niri-fx}
case "$package_name" in
    niri-fx|niri-fx-git) ;;
    *) printf '%s\n' 'Package must be niri-fx or niri-fx-git.' >&2; exit 2 ;;
esac
# The marker alone does not establish which package manager is safe to use.
# shellcheck source=/dev/null
source /etc/os-release
if [[ $ID != arch ]]; then
    printf '%s\n' 'This acceptance check requires an official Arch Linux container.' >&2
    exit 2
fi

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=$(realpath -m -- "$1")
mkdir -p -- "$output"
if [[ -e $output/acceptance.log ]]; then
    printf '%s\n' 'Use a fresh output directory to preserve earlier acceptance evidence.' >&2
    exit 2
fi
exec > >(tee "$output/acceptance.log") 2>&1

pacman -Syu --noconfirm --needed base-devel python-build python-installer \
    python-setuptools python-wheel niri git python-pillow desktop-file-utils namcap \
    hicolor-icon-theme
if pacman -Q niri-fx >/dev/null 2>&1 || pacman -Q niri-fx-git >/dev/null 2>&1; then
    printf '%s\n' 'The disposable container must not already contain a NiriFX package.' >&2
    exit 1
fi
pacman -Q > "$output/container-packages.txt"

work=$(mktemp -d /tmp/nirifx-arch-package.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
chmod 755 "$work"
useradd --system --user-group --home-dir "$work/build-home" --create-home nirifx-build
mkdir "$work/recipe" "$work/smoke-home" "$work/smoke-output"
for file in PKGBUILD .SRCINFO niri-fx-studio.desktop README.Arch LICENSE REUSE.toml; do
    cp "$repo/packaging/arch/$package_name/$file" "$work/recipe/"
done
# Existing synthetic settings catch removal as well as unexpected file creation.
mkdir -p "$work/smoke-home/.config/niri" "$work/smoke-home/.local/share/niri-fx"
printf '%s\n' 'animations { slowdown 1.0; }' > "$work/smoke-home/.config/niri/config.kdl"
printf '%s\n' '{"keep":"saved profile fixture"}' > "$work/smoke-home/.local/share/niri-fx/saved.json"
chown -R nirifx-build:nirifx-build "$work/recipe" "$work/smoke-home" "$work/smoke-output"

# Neither package building nor installed smoke tests inherit a desktop connection,
# Python import path, personal HOME or package-manager configuration from the host.
as_builder() {
    runuser -u nirifx-build -- env -i HOME="$work/build-home" PATH=/usr/bin \
        LANG=C.UTF-8 "$@"
}
as_user() {
    runuser -u nirifx-build -- env -i HOME="$work/smoke-home" PATH=/usr/bin \
        LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 "$@"
}

cd "$work/recipe"
as_builder makepkg --printsrcinfo > "$output/generated.SRCINFO"
diff -u .SRCINFO "$output/generated.SRCINFO"
as_builder makepkg --cleanbuild --noconfirm
# VCS pkgver() may update the copied recipe after fetching the current branch.
# Keep both the submitted metadata check and the resolved build metadata.
as_builder makepkg --printsrcinfo > "$output/resolved.SRCINFO"
if [[ $package_name == niri-fx-git ]]; then
    as_builder git -C "$work/recipe/src/niri-fx" rev-parse --verify HEAD > "$output/resolved-commit.txt"
fi
# --packagelist predicts a debug archive even when there were no native symbols
# and makepkg correctly omitted that archive. Count only files actually built.
# A regular redirect also preserves makepkg's exit status under set -e.
as_builder makepkg --packagelist > "$output/expected-packages.txt"
packages=()
while IFS= read -r candidate; do
    if [[ -f $candidate ]]; then
        packages+=("$candidate")
    fi
done < "$output/expected-packages.txt"
if [[ ${#packages[@]} != 1 ]]; then
    printf 'Expected exactly one built %s package.\n' "$package_name" >&2
    cat "$output/expected-packages.txt" >&2
    exit 1
fi
package=${packages[0]}
# Keep a completed build available even when a later acceptance check fails.
cp "$package" "$output/"
(cd "$output" && sha256sum "$(basename "$package")") > "$output/package.sha256"
namcap PKGBUILD | tee "$output/namcap-pkgbuild.txt"
namcap "$package" | tee "$output/namcap-package.txt"
# namcap reports findings in its output and may still return success.
if grep -qE '(^| )E: ' "$output/namcap-pkgbuild.txt" "$output/namcap-package.txt"; then
    printf '%s\n' 'Resolve namcap errors before publishing this package.' >&2
    exit 1
fi
python "$repo/scripts/check-arch-package.py" "$package" > "$output/package-check.json"

# Capture stock Niri files, including symlink targets, modes and missing files.
# Pacman marks shared directories with a trailing slash; minimal Arch images may
# omit them and adding unrelated files beneath them must not affect this check.
cat > "$work/snapshot.py" <<'PY'
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

if sys.argv[1] == "niri":
    owned = subprocess.check_output(["pacman", "-Qql", "niri"], text=True).splitlines()
    paths = [Path(p) for p in owned if not p.endswith("/")]
    version = subprocess.check_output(["pacman", "-Q", "niri"], text=True).strip()
else:
    paths = sorted(Path(sys.argv[1]).rglob("*"))
    version = None
records = []
for path in paths:
    record = {"path": str(path)}
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        record["missing"] = True
        records.append(record)
        continue
    record.update(mode=metadata.st_mode, uid=metadata.st_uid, gid=metadata.st_gid)
    if stat.S_ISLNK(metadata.st_mode):
        record["target"] = str(path.readlink())
    elif stat.S_ISREG(metadata.st_mode):
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    records.append(record)
print(json.dumps({"version": version, "files": records}, indent=2, sort_keys=True))
PY
python "$work/snapshot.py" niri > "$output/niri-before.json"
python "$work/snapshot.py" "$work/smoke-home" > "$output/user-before.json"
pacman -U --noconfirm "$package"
pacman -Q "$package_name" > "$output/installed-version.txt"
python "$work/snapshot.py" niri > "$output/niri-installed.json"
cmp "$output/niri-before.json" "$output/niri-installed.json"

cd "$work/smoke-output"
as_user /usr/bin/niri-fx --version
as_user /usr/bin/niri-fx profile --fragment-preset tear > "$output/profile.json"
as_user /usr/bin/niri-fx render --custom "$output/profile.json" > "$output/stock.kdl"
as_user /usr/bin/niri validate --config "$output/stock.kdl"
as_user /usr/bin/niri-fx preview --custom "$output/profile.json" --output "$work/smoke-output/studio.html"
desktop-file-validate /usr/share/applications/niri-fx-studio.desktop
as_user /usr/bin/python -I -B - "$output/profile.json" <<'PY'
import json
from pathlib import Path
import sys

import niri_fx
from niri_fx.documents import load_document, parse_document

package = Path(niri_fx.__file__).resolve().parent
assert package.is_relative_to(Path("/usr/lib")), package
for resource in (
    "preview.html", "effect-core.js", "studio.js", "studio.css",
    "assets/niri-fx.svg", "qml/shell.qml", "gtk/app.mjs",
    "agent_data/nirifx/SKILL.md",
):
    assert (package / resource).is_file(), resource
assert list((package / "shaders").glob("*.glsl"))
document = load_document(Path(sys.argv[1]))
assert document["schema"] == 4 and document["fragment_motion"]["batches"] > 0
parse_document(document)
assert Path("studio.html").stat().st_size > 100_000
print(json.dumps({"installed_version": niri_fx.__version__, "installed_resources": "passed", "portable_profile": "passed"}))
PY
python "$work/snapshot.py" "$work/smoke-home" > "$output/user-installed.json"
cmp "$output/user-before.json" "$output/user-installed.json"

pacman -Qql "$package_name" > "$output/installed-files.txt"
pacman -R --noconfirm "$package_name"
if pacman -Q "$package_name" >/dev/null 2>&1; then
    printf '%s\n' 'Package removal did not complete.' >&2
    exit 1
fi
as_user /usr/bin/python -I -B - <<'PY'
import importlib.util
from pathlib import Path

assert importlib.util.find_spec("niri_fx") is None
for path in (
    "/usr/bin/niri-fx", "/usr/share/applications/niri-fx-studio.desktop",
    "/usr/share/icons/hicolor/scalable/apps/niri-fx.svg",
    "/usr/share/licenses/niri-fx", "/usr/share/licenses/niri-fx-git",
    "/usr/share/doc/niri-fx",
):
    assert not Path(path).exists(), path
PY
python "$work/snapshot.py" niri > "$output/niri-removed.json"
python "$work/snapshot.py" "$work/smoke-home" > "$output/user-removed.json"
cmp "$output/niri-before.json" "$output/niri-removed.json"
cmp "$output/user-before.json" "$output/user-removed.json"
printf 'PASS %s: clean build, metadata, payload, installed CLI/Studio resources, stock Niri coexistence and removal.\n' "$package_name"
