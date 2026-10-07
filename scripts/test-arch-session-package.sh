#!/usr/bin/env bash
# Audit/install a complete archive only inside a disposable Arch container.
set -euo pipefail

if [[ ${NIRIFX_ARCH_PACKAGE_CONTAINER:-} != 1 ]] ||
    [[ ! -f /.dockerenv && ! -f /run/.containerenv ]]; then
    printf '%s\n' 'Refusing host execution: use a disposable container with NIRIFX_ARCH_PACKAGE_CONTAINER=1.' >&2
    exit 2
fi
if [[ $EUID != 0 || $# -lt 2 ]]; then
    printf '%s\n' 'Usage as container root: test-arch-session-package.sh OUTPUT PACKAGE_ARCHIVE [REPLACEMENT_ARCHIVE] [--previous-tools-archive OLD_TOOLS]' >&2
    exit 2
fi
output_argument=$1
package_argument=$2
replacement_argument=$2
previous_tools=
shift 2
if [[ $# -gt 0 && $1 != --* ]]; then
    replacement_argument=$1
    shift
fi
if [[ $# -gt 0 ]]; then
    if [[ $# != 2 || $1 != --previous-tools-archive ]]; then
        printf '%s\n' 'Only --previous-tools-archive OLD_TOOLS may follow the archive arguments.' >&2
        exit 2
    fi
    previous_tools=$2
fi
# shellcheck source=/dev/null
source /etc/os-release
if [[ $ID != arch ]]; then
    printf '%s\n' 'This acceptance check requires a disposable official Arch Linux container.' >&2
    exit 2
fi
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=$(realpath -m -- "$output_argument")
mkdir -p -- "$output"
if [[ -e $output/acceptance.log ]]; then
    printf '%s\n' 'Use a fresh output directory to preserve earlier acceptance evidence.' >&2
    exit 2
fi
exec > >(tee "$output/acceptance.log") 2>&1
for package in niri-fx niri-fx-git; do
    if pacman -Q "$package" >/dev/null 2>&1; then
        printf '%s\n' 'The disposable container must not already contain NiriFX packages.' >&2
        exit 1
    fi
done
mkdir "$output/archives"
cp -- "$package_argument" "$output/archives/package.pkg.tar.zst"
# Reinstalling the same archive is the minimum package-replacement check. An
# explicit replacement archive can exercise distinct tools/native identities,
# including same-version builds. The report distinguishes each identity.
cp -- "$replacement_argument" "$output/archives/replacement.pkg.tar.zst"
if [[ -n $previous_tools ]]; then
    cp -- "$previous_tools" "$output/archives/previous-tools.pkg.tar.zst"
fi
chmod 644 "$output"/archives/*.pkg.tar.zst
(cd "$output/archives" && sha256sum -- *.pkg.tar.zst) > "$output/archives.sha256"

# No compilation/source fetch occurs here. Audit the complete archive before
# pacman can install it; the allowlist rejects install scripts and system hooks.
pacman -Syu --noconfirm --needed niri python bash systemd dbus wayland libglvnd \
    hicolor-icon-theme zstd desktop-file-utils
pacman -Q > "$output/container-packages.txt"
python "$repo/scripts/check-arch-package.py" "$output/archives/package.pkg.tar.zst" \
    > "$output/package-check.json"
python "$repo/scripts/check-arch-package.py" "$output/archives/replacement.pkg.tar.zst" \
    > "$output/replacement-check.json"
package_name=$(python - "$output/package-check.json" "$output/replacement-check.json" <<'PY_PACKAGE'
import json
from pathlib import Path
import sys

first, replacement = (json.loads(Path(path).read_text()) for path in sys.argv[1:])
assert first["pkgname"] in {"niri-fx", "niri-fx-git"}
assert replacement["pkgname"] == first["pkgname"], "Use a replacement of the same package"
print(first["pkgname"])
PY_PACKAGE
)

if [[ -n $previous_tools ]]; then
    # This opt-in fixture is a previously audited tools-only archive, not a new
    # full-session candidate. Bind its identity and reject install hooks before
    # using it to exercise package-manager file ownership during the upgrade.
    bsdtar -tf "$output/archives/previous-tools.pkg.tar.zst" > "$output/previous-tools-files.txt"
    bsdtar -xOf "$output/archives/previous-tools.pkg.tar.zst" .PKGINFO > "$output/previous-tools.PKGINFO"
    python - "$output" "$package_name" <<'PY_PREVIOUS'
from pathlib import Path, PurePosixPath
import sys

output = Path(sys.argv[1])
for name in (output / "previous-tools-files.txt").read_text().splitlines():
    path = PurePosixPath(name)
    assert not path.is_absolute() and ".." not in path.parts, name
    assert path.name != ".INSTALL" and "hooks" not in path.parts, name
fields = {}
for line in (output / "previous-tools.PKGINFO").read_text().splitlines():
    if " = " in line:
        key, value = line.split(" = ", 1)
        fields.setdefault(key, []).append(value)
assert fields.get("pkgname") == [sys.argv[2]], "Old tools must match the package channel"
assert fields.get("arch") == ["any"], "Expected the earlier tools-only archive"
assert len(fields.get("pkgver", [])) == 1 and fields["pkgver"][0].startswith("0.21.0")
PY_PREVIOUS
fi

work=$(mktemp -d /tmp/nirifx-arch-session.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
chmod 755 "$work"
for account in a b; do
    useradd --system --user-group --home-dir "$work/home-$account" --create-home "nirifx-session-$account"
    mkdir -p "$work/home-$account/.config/niri" "$work/home-$account/.local/share/niri-fx"
    printf '%s\n' 'animations { slowdown 1.0; }' > "$work/home-$account/.config/niri/config.kdl"
    printf '{"keep":"synthetic settings %s"}\n' "$account" > "$work/home-$account/.local/share/niri-fx/saved.json"
    chown -R "nirifx-session-$account:nirifx-session-$account" "$work/home-$account"
done
as_user() {
    local account=$1
    shift
    runuser -u "nirifx-session-$account" -- env -i HOME="$work/home-$account" \
        PATH=/usr/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 timeout 180s "$@"
}
# Record file identities, ownership and modes. Shared package directories are
# intentionally excluded from stock-file checks; unrelated files may coexist.
cat > "$work/snapshot.py" <<'PY'
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

root = Path(sys.argv[1])
if sys.argv[1] == "niri":
    owned = subprocess.check_output(["pacman", "-Qql", "niri"], text=True).splitlines()
    paths = [Path(p) for p in owned if not p.endswith("/")]
    version = subprocess.check_output(["pacman", "-Q", "niri"], text=True).strip()
else:
    paths = sorted(root.rglob("*"))
    version = None
records = []
for path in paths:
    item = {"path": str(path) if version else str(path.relative_to(root))}
    try:
        info = path.lstat()
    except FileNotFoundError:
        item["missing"] = True
    else:
        item.update(mode=info.st_mode, uid=info.st_uid, gid=info.st_gid)
        if stat.S_ISREG(info.st_mode):
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            item["target"] = str(path.readlink())
    records.append(item)
print(json.dumps({"version": version, "files": records}, sort_keys=True, indent=2))
PY
snapshot() { python "$work/snapshot.py" "$1" > "$2"; }
acceptance_helper="$repo/scripts/lib/arch_session_acceptance.py"
capture() { as_user "$1" /usr/bin/python -I -B "$acceptance_helper" capture > "$2"; }
reviewed_apply() {
    local account=$1 label=$2 fingerprint
    shift 2
    snapshot "$work/home-$account" "$output/$label-before-review.json"
    as_user "$account" /usr/bin/niri-fx "$@" > "$output/$label-plan.json"
    snapshot "$work/home-$account" "$output/$label-after-review.json"
    cmp "$output/$label-before-review.json" "$output/$label-after-review.json"
    fingerprint=$(python "$acceptance_helper" plan "$output/$label-plan.json" "$work/home-$account")
    as_user "$account" /usr/bin/niri-fx "$@" --apply --expect-plan "$fingerprint" \
        > "$output/$label-applied.json"
    if [[ $account == a && -f $output/user-b-ready.json ]]; then
        snapshot "$work/home-b" "$output/$label-other-user.json"
        cmp "$output/user-b-ready.json" "$output/$label-other-user.json"
    fi
}
snapshot niri "$output/niri-before.json"
for account in a b; do
    snapshot "$work/home-$account" "$output/user-$account-before.json"
done
if [[ -n $previous_tools ]]; then
    pacman -U --noconfirm "$output/archives/previous-tools.pkg.tar.zst"
    pacman -Q "$package_name" > "$output/previous-tools-installed-version.txt"
    snapshot niri "$output/niri-previous-tools.json"
    cmp "$output/niri-before.json" "$output/niri-previous-tools.json"
    for account in a b; do
        snapshot "$work/home-$account" "$output/user-$account-previous-tools.json"
        cmp "$output/user-$account-before.json" "$output/user-$account-previous-tools.json"
    done
fi
pacman -U --noconfirm "$output/archives/package.pkg.tar.zst"
pacman -Q "$package_name" > "$output/installed-versions.txt"
snapshot niri "$output/niri-installed.json"
cmp "$output/niri-before.json" "$output/niri-installed.json"
cd "$work"
for account in a b; do
    snapshot "$work/home-$account" "$output/user-$account-installed.json"
    cmp "$output/user-$account-before.json" "$output/user-$account-installed.json"
done
mkdir "$work/smoke-output"
chown nirifx-session-a:nirifx-session-a "$work/smoke-output"
cd "$work/smoke-output"
as_user a /usr/bin/niri-fx --version
as_user a /usr/bin/niri-fx profile --fragment-preset tear > "$output/profile.json"
as_user a /usr/bin/niri-fx render --custom "$output/profile.json" > "$output/stock.kdl"
as_user a /usr/bin/niri validate --config "$output/stock.kdl"
as_user a /usr/bin/niri-fx preview --custom "$output/profile.json" --output "$work/smoke-output/studio.html"
desktop-file-validate /usr/share/applications/niri-fx-studio.desktop
as_user a /usr/bin/python -I -B - "$output/profile.json" <<'PY_RESOURCES'
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
PY_RESOURCES
snapshot "$work/home-a" "$output/user-a-tools-smoke.json"
cmp "$output/user-a-before.json" "$output/user-a-tools-smoke.json"

# An unprepared user's chooser must fail without selecting, adopting, or trying
# to start stock systemd. Only this refusal path calls the login dispatcher.
if as_user b /usr/bin/niri-fx-session > "$output/unprepared-dispatch.txt" 2>&1; then
    printf '%s\n' 'Unprepared dispatcher unexpectedly succeeded.' >&2
    exit 1
fi
grep -q 'Use stock Niri' "$output/unprepared-dispatch.txt"
snapshot "$work/home-b" "$output/user-b-unprepared.json"
cmp "$output/user-b-before.json" "$output/user-b-unprepared.json"

for account in a b; do
    config="$work/home-$account/.config/niri/config.kdl"
    as_user "$account" /usr/bin/niri-fx native adopt --config "$config" > "$output/adopt-$account-plan.json"
    snapshot "$work/home-$account" "$output/user-$account-reviewed.json"
    cmp "$output/user-$account-before.json" "$output/user-$account-reviewed.json"
    plan=$(python - "$output/adopt-$account-plan.json" "$work/home-$account" <<'PY'
import json
from pathlib import Path
import re
import sys

result = json.loads(Path(sys.argv[1]).read_text())
assert result["dry_run"] is True and result["changes"]
assert re.fullmatch(r"[0-9a-f]{64}", result["plan_sha256"])
assert all(Path(item["path"]).is_relative_to(Path(sys.argv[2])) for item in result["changes"])
print(result["plan_sha256"])
PY
)
    bad_plan="0${plan:1}"
    if [[ $plan == 0* ]]; then bad_plan="1${plan:1}"; fi
    if as_user "$account" /usr/bin/niri-fx native adopt --config "$config" --apply \
        --expect-plan "$bad_plan" > "$output/adopt-$account-stale.txt" 2>&1; then
        printf '%s\n' 'An incorrect plan fingerprint unexpectedly applied.' >&2
        exit 1
    fi
    snapshot "$work/home-$account" "$output/user-$account-stale.json"
    cmp "$output/user-$account-before.json" "$output/user-$account-stale.json"
    as_user "$account" /usr/bin/niri-fx native adopt --config "$config" --apply --expect-plan "$plan" \
        > "$output/adopt-$account-applied.json"
    # The retained CLI exercises copied Python resources outside site-packages.
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" native status --offline \
        > "$output/retained-$account-status.json"
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" --version \
        > "$output/retained-$account-version.txt"
    as_user "$account" /usr/bin/python -I -B - <<'PY'
import hashlib
import json
import os
from pathlib import Path

home = Path.home()
root = home / ".local/share/niri-fx/native"
selection = json.loads((root / "selection.json").read_text())
bundle = root / "bundles" / selection["selected"]
installed = Path("/usr/lib/niri-fx/session-candidate/bin/niri")
retained = bundle / "bin/niri"
assert installed.read_bytes() == retained.read_bytes()
assert not os.path.samefile(installed, retained)
assert retained.stat().st_uid == os.getuid()
assert (bundle / "config.kdl").read_bytes() == (home / ".config/niri/config.kdl").read_bytes()
tools = json.loads((root / "tools/selection.json").read_text())
record = json.loads((root / "tools/runtimes" / f"{tools['current']}.json").read_text())
assert record["schema"] == 2
assert Path(record["package"]).is_relative_to(root / "tools/packages")
for name, digest in record["files"].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest
print("Retained executable/config/tools are independent, private, and byte-matched.")
PY
    snapshot "$work/home-$account" "$output/user-$account-adopted.json"
done
# A owns a saved continuous recipe; B keeps its plain native configuration.
# Re-adoption must preserve actual choices, not only a blank baseline snapshot.
initial_a=$(python - "$output/adopt-a-applied.json" <<'PY_ID'
import json
from pathlib import Path
import sys
print(json.loads(Path(sys.argv[1]).read_text())["selection"]["selected"])
PY_ID
)
reviewed_apply a configure-a native configure "$initial_a" --document "$output/profile.json"
for account in a b; do
    capture "$account" "$output/state-$account-ready.json"
    snapshot "$work/home-$account" "$output/user-$account-ready.json"
done
python - "$output/state-a-ready.json" "$output/state-b-ready.json" <<'PY_RECIPES'
import json
from pathlib import Path
import sys

a, b = (json.loads(Path(path).read_text()) for path in sys.argv[1:])
assert a["customization"] is not None and b["customization"] is None
assert a["config_files"] != b["config_files"]
PY_RECIPES
snapshot niri "$output/niri-adopted.json"
cmp "$output/niri-before.json" "$output/niri-adopted.json"

# Package replacement must never adopt a new runtime or alter user selection.
pacman -U --noconfirm "$output/archives/replacement.pkg.tar.zst"
pacman -Q "$package_name" > "$output/replacement-versions.txt"
for account in a b; do
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" native status --offline \
        > "$output/retained-$account-after-replacement.json"
    snapshot "$work/home-$account" "$output/user-$account-replaced.json"
    cmp "$output/user-$account-ready.json" "$output/user-$account-replaced.json"
done
# Only A explicitly adopts the replacement. B's retained settings and selected
# tools must remain byte-identical throughout A's independent transactions.
reviewed_apply a readopt-a native adopt
capture a "$output/state-a-readopted.json"
snapshot "$work/home-a" "$output/user-a-readopted.json"
snapshot "$work/home-b" "$output/user-b-after-readoption.json"
cmp "$output/user-b-ready.json" "$output/user-b-after-readoption.json"
python "$acceptance_helper" assess "$output" > "$output/upgrade-assessment-initial.json"
native_changed=$(python -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["native_identity_changed"]))' "$output/upgrade-assessment.json")
tools_changed=$(python -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["tools_content_changed"]))' "$output/upgrade-assessment.json")
if [[ $native_changed == 1 ]]; then
    reviewed_apply a compositor-rollback native rollback
    capture a "$output/state-a-compositor-rollback.json"
    reviewed_apply a compositor-rollforward native rollback
    capture a "$output/state-a-compositor-rollforward.json"
fi
if [[ $tools_changed == 1 ]]; then
    reviewed_apply a tools-rollback native tools-rollback \
        --registered-entry /usr/share/wayland-sessions/niri-fx-packaged.desktop
    capture a "$output/state-a-tools-rollback.json"
    reviewed_apply a tools-rollforward native tools-rollback \
        --registered-entry /usr/share/wayland-sessions/niri-fx-packaged.desktop
    capture a "$output/state-a-tools-rollforward.json"
fi
capture a "$output/state-a-final.json"
python "$acceptance_helper" rollback "$output"
for account in a b; do
    snapshot "$work/home-$account" "$output/user-$account-retained-final.json"
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" --version \
        > "$output/retained-$account-final-version.txt"
done
cmp "$output/user-b-ready.json" "$output/user-b-retained-final.json"
snapshot niri "$output/niri-readopted.json"
cmp "$output/niri-before.json" "$output/niri-readopted.json"
if [[ ${NIRIFX_ARCH_SESSION_DEPENDENCIES:-} == 1 ]]; then
    python "$repo/scripts/lib/arch_session_dependencies.py" \
        "$output/dependencies" "$work/home-a" "$work/home-b"
fi
pacman -R --noconfirm "$package_name"

for path in /usr/bin/niri-fx-session /usr/bin/niri-fx \
    /usr/share/wayland-sessions/niri-fx-packaged.desktop /usr/lib/niri-fx/session-candidate \
    /usr/share/applications/niri-fx-studio.desktop /usr/share/icons/hicolor/scalable/apps/niri-fx.svg \
    /usr/share/doc/niri-fx "/usr/share/licenses/$package_name"; do
    if [[ -e $path || -L $path ]]; then
        printf 'Package-owned path remains after removal: %s\n' "$path" >&2
        exit 1
    fi
done
as_user a /usr/bin/python -I -B - <<'PY_REMOVED'
import importlib.util
assert importlib.util.find_spec("niri_fx") is None
PY_REMOVED

for account in a b; do
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" native status --offline \
        > "$output/retained-$account-after-removal.json"
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" --version \
        > "$output/retained-$account-after-removal-version.txt"
    cmp "$output/retained-$account-final-version.txt" "$output/retained-$account-after-removal-version.txt"
    snapshot "$work/home-$account" "$output/user-$account-removed.json"
    cmp "$output/user-$account-retained-final.json" "$output/user-$account-removed.json"
done
snapshot niri "$output/niri-removed.json"
cmp "$output/niri-before.json" "$output/niri-removed.json"
printf '%s\n' 'PASS: audited complete package, install/replacement, two-user adoption, explicit re-adoption and applicable rollback, retained CLI after removal, and unchanged stock Niri files.'
printf '%s\n' 'No compositor session was launched. Display-manager/systemd lifecycle, portals and physical desktop acceptance remain separate gates.'
