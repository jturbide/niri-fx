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
for baseline in "${NIRIFX_ARCH_PREVIOUS_SESSION_ARCHIVE:-}" "${NIRIFX_ARCH_PREVIOUS_TOOLS_ARCHIVE:-}"; do
    if [[ -n $baseline && ( ! -f $baseline || ! -r $baseline ) ]]; then
        printf 'Baseline archive is not a readable file: %s\n' "$baseline" >&2
        exit 2
    fi
done

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
    hicolor-icon-theme rust clang libdisplay-info libinput libpipewire \
    libxkbcommon mesa pango pixman seatd systemd-libs wayland libglvnd
if pacman -Q niri-fx >/dev/null 2>&1 || pacman -Q niri-fx-git >/dev/null 2>&1; then
    printf '%s\n' 'The disposable container must not already contain a NiriFX package.' >&2
    exit 1
fi
pacman -Q > "$output/container-packages.txt"

work=$(mktemp -d /tmp/nirifx-arch-package.XXXXXXXX)
cleanup() {
    local attempt metadata
    if [[ -d $work/recipe/src/attempts ]]; then
        mkdir -p "$output/native-builds"
        for attempt in "$work/recipe/src/attempts"/*; do
            [[ -d $attempt ]] || continue
            mkdir -p "$output/native-builds/$(basename "$attempt")"
            for metadata in attempt.json manifest.json; do
                if [[ -f $attempt/$metadata ]]; then
                    cp "$attempt/$metadata" "$output/native-builds/$(basename "$attempt")/"
                fi
            done
            if [[ -d $attempt/logs ]]; then
                cp -r "$attempt/logs" "$output/native-builds/$(basename "$attempt")/"
            fi
        done
    fi
    rm -rf -- "$work"
}
trap cleanup EXIT
chmod 755 "$work"
useradd --system --user-group --home-dir "$work/build-home" --create-home nirifx-build
mkdir "$work/recipe"
for file in PKGBUILD .SRCINFO niri-fx-studio.desktop niri-fx-packaged.desktop README.Arch LICENSE REUSE.toml; do
    cp "$repo/packaging/arch/$package_name/$file" "$work/recipe/"
done
chown -R nirifx-build:nirifx-build "$work/recipe"

# Never silently build old published sources while a PR changes the product.
# The original recipe remains unchanged; only its disposable copy is overridden.
git_repo() { GIT_OPTIONAL_LOCKS=0 git -c safe.directory="$repo" -C "$repo" "$@"; }
checkout_status=$(git_repo status --porcelain --untracked-files=normal)
if [[ -n $checkout_status ]]; then
    printf '%s\n' 'Candidate acceptance requires a clean checkout, including untracked source files.' >&2
    exit 1
fi
source_commit=$(git_repo rev-parse --verify HEAD)
source_tree=$(git_repo rev-parse 'HEAD^{tree}')
git -c safe.directory="$repo" -c safe.directory="$repo/.git" \
    clone --bare --no-hardlinks -- "$repo" "$work/nirifx-source.git"
chown -R nirifx-build:nirifx-build "$work/nirifx-source.git"

# Build tools never inherit a desktop connection, personal HOME, Python import
# path or Cargo cache. CI limits compiler concurrency to fit its memory budget.
as_builder() {
    runuser -u nirifx-build -- env -i HOME="$work/build-home" PATH=/usr/bin \
        LANG=C.UTF-8 CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}" "$@"
}

cd "$work/recipe"
as_builder makepkg --printsrcinfo > "$output/generated.SRCINFO"
diff -u .SRCINFO "$output/generated.SRCINFO"
cp PKGBUILD "$output/submitted.PKGBUILD"
printf "\n# Acceptance-only source override: test the reviewed checkout commit.\nsource[0]='niri-fx::git+file://%s#commit=%s'\nsha256sums[0]='SKIP'\n" \
    "$work/nirifx-source.git" "$source_commit" >> PKGBUILD
as_builder makepkg --printsrcinfo > "$output/candidate.SRCINFO"
python - "$output" "$package_name" "$source_commit" "$source_tree" <<'PY_SOURCE'
import json
from pathlib import Path
import sys

output = Path(sys.argv[1])
def sources(name):
    return [line.strip().removeprefix("source = ")
            for line in (output / name).read_text().splitlines()
            if line.strip().startswith("source = ")]
original, candidate = sources("generated.SRCINFO"), sources("candidate.SRCINFO")
assert len(original) == len(candidate) and original[1:] == candidate[1:]
assert original[0].startswith("niri-fx::git+https://github.com/jturbide/niri-fx.git#")
assert candidate[0].endswith("#commit=" + sys.argv[3])
(output / "source-substitution.json").write_text(json.dumps({
    "package": sys.argv[2], "scope": "candidate checkout; not the published tag or moving remote",
    "checkout_commit": sys.argv[3], "checkout_tree": sys.argv[4],
    "original": original[0], "replacement": candidate[0],
    "remaining_sources_unchanged": True,
}, indent=2) + "\n")
PY_SOURCE
as_builder makepkg --cleanbuild --noconfirm
# VCS pkgver() may update the copied recipe after fetching the current branch.
# Keep both the submitted metadata check and the resolved build metadata.
as_builder makepkg --printsrcinfo > "$output/resolved.SRCINFO"
as_builder git -C "$work/recipe/src/niri-fx" rev-parse --verify HEAD > "$output/resolved-commit.txt"
[[ $(cat "$output/resolved-commit.txt") == "$source_commit" ]]
[[ $(git_repo rev-parse --verify HEAD) == "$source_commit" ]]
checkout_status=$(git_repo status --porcelain --untracked-files=normal)
if [[ -n $checkout_status ]]; then
    printf '%s\n' 'The source checkout changed during the build; candidate acceptance is incomplete.' >&2
    exit 1
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
namcap "$output/submitted.PKGBUILD" | tee "$output/namcap-pkgbuild.txt"
namcap "$package" | tee "$output/namcap-package.txt"
# namcap reports findings in its output and may still return success.
if grep -qE '(^| )E: ' "$output/namcap-pkgbuild.txt" "$output/namcap-package.txt"; then
    printf '%s\n' 'Resolve namcap errors before publishing this package.' >&2
    exit 1
fi
python "$repo/scripts/check-arch-package.py" "$package" > "$output/package-check.json"

# The installed archive audit owns stock-file snapshots, two synthetic users,
# reviewed adoption and removal. It never launches a compositor or login session.
session_args=("$output/session" "$package")
if [[ -n ${NIRIFX_ARCH_PREVIOUS_SESSION_ARCHIVE:-} ]]; then
    # Install and adopt the baseline first, then review the freshly built package
    # as an update. Both archives are audited before either is installed.
    session_args=("$output/session" "$NIRIFX_ARCH_PREVIOUS_SESSION_ARCHIVE" "$package")
fi
if [[ -n ${NIRIFX_ARCH_PREVIOUS_TOOLS_ARCHIVE:-} ]]; then
    session_args+=(--previous-tools-archive "$NIRIFX_ARCH_PREVIOUS_TOOLS_ARCHIVE")
fi
bash "$repo/scripts/test-arch-session-package.sh" "${session_args[@]}"
printf 'PASS %s: exact-checkout clean build, submitted/resolved metadata, complete payload and container adoption/removal.\n' "$package_name"
