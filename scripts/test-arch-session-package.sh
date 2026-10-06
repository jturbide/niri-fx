#!/usr/bin/env bash
# Audit/install supplied archives only inside a disposable Arch container.
set -euo pipefail

if [[ ${NIRIFX_ARCH_PACKAGE_CONTAINER:-} != 1 ]] ||
    [[ ! -f /.dockerenv && ! -f /run/.containerenv ]]; then
    printf '%s\n' 'Refusing host execution: use a disposable container with NIRIFX_ARCH_PACKAGE_CONTAINER=1.' >&2
    exit 2
fi
if [[ $EUID != 0 || ( $# != 3 && $# != 5 ) ]]; then
    printf '%s\n' 'Usage as container root: test-arch-session-package.sh OUTPUT TOOLS_ARCHIVE COMPOSITOR_ARCHIVE [UPGRADE_TOOLS UPGRADE_COMPOSITOR]' >&2
    exit 2
fi
# shellcheck source=/dev/null
source /etc/os-release
if [[ $ID != arch ]]; then
    printf '%s\n' 'This acceptance check requires a disposable official Arch Linux container.' >&2
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
for package in niri-fx niri-fx-git niri-fx-compositor-git; do
    if pacman -Q "$package" >/dev/null 2>&1; then
        printf '%s\n' 'The disposable container must not already contain NiriFX packages.' >&2
        exit 1
    fi
done
mkdir "$output/archives"
cp -- "$2" "$output/archives/tools.pkg.tar.zst"
cp -- "$3" "$output/archives/compositor.pkg.tar.zst"
if [[ $# == 5 ]]; then
    cp -- "$4" "$output/archives/upgrade-tools.pkg.tar.zst"
    cp -- "$5" "$output/archives/upgrade-compositor.pkg.tar.zst"
fi
chmod 644 "$output"/archives/*.pkg.tar.zst
(cd "$output/archives" && sha256sum -- *.pkg.tar.zst) > "$output/archives.sha256"

# No package compilation or source fetch occurs here. Validate exact archives
# before pacman can install them; their payload allowlists reject .INSTALL/hooks.
pacman -Syu --noconfirm --needed niri python bash systemd dbus wayland libglvnd \
    hicolor-icon-theme zstd
pacman -Q > "$output/container-packages.txt"
python "$repo/scripts/check-arch-package.py" "$output/archives/tools.pkg.tar.zst" \
    > "$output/tools-check.json"
python "$repo/scripts/check-arch-session-package.py" "$output/archives/compositor.pkg.tar.zst" \
    --tools-package "$output/archives/tools.pkg.tar.zst" > "$output/session-check.json"
if [[ $# == 5 ]]; then
    python "$repo/scripts/check-arch-package.py" "$output/archives/upgrade-tools.pkg.tar.zst" \
        > "$output/upgrade-tools-check.json"
    python "$repo/scripts/check-arch-session-package.py" "$output/archives/upgrade-compositor.pkg.tar.zst" \
        --tools-package "$output/archives/upgrade-tools.pkg.tar.zst" > "$output/upgrade-session-check.json"
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
snapshot niri "$output/niri-before.json"
for account in a b; do
    snapshot "$work/home-$account" "$output/user-$account-before.json"
done
pacman -U --noconfirm "$output/archives/tools.pkg.tar.zst" "$output/archives/compositor.pkg.tar.zst"
pacman -Q niri-fx-git niri-fx-compositor-git > "$output/installed-versions.txt"
snapshot niri "$output/niri-installed.json"
cmp "$output/niri-before.json" "$output/niri-installed.json"
cd "$work"
for account in a b; do
    snapshot "$work/home-$account" "$output/user-$account-installed.json"
    cmp "$output/user-$account-before.json" "$output/user-$account-installed.json"
done
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
snapshot niri "$output/niri-adopted.json"
cmp "$output/niri-before.json" "$output/niri-adopted.json"

if [[ $# == 5 ]]; then
    # No adoption follows the package replacement. Both users must keep the old
    # selection and bytes until they independently review a new adoption plan.
    pacman -U --noconfirm "$output/archives/upgrade-tools.pkg.tar.zst" "$output/archives/upgrade-compositor.pkg.tar.zst"
    pacman -Q niri-fx-git niri-fx-compositor-git > "$output/replacement-versions.txt"
    for account in a b; do
        as_user "$account" "$work/home-$account/.local/bin/niri-fx" native status --offline \
            > "$output/retained-$account-after-replacement.json"
        snapshot "$work/home-$account" "$output/user-$account-replaced.json"
        cmp "$output/user-$account-adopted.json" "$output/user-$account-replaced.json"
    done
    printf '%s\n' 'Package replacement retained both user selections; explicit upgrade adoption was not exercised.'
else
    printf '%s\n' 'Package replacement not assessed: supply the optional second archive pair to exercise it.'
fi
pacman -R --noconfirm niri-fx-compositor-git niri-fx-git
for path in /usr/bin/niri-fx-session /usr/bin/niri-fx \
    /usr/share/wayland-sessions/niri-fx-packaged.desktop /usr/lib/niri-fx/session-candidate; do
    if [[ -e $path || -L $path ]]; then
        printf 'Package-owned path remains after removal: %s\n' "$path" >&2
        exit 1
    fi
done
for account in a b; do
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" native status --offline \
        > "$output/retained-$account-after-removal.json"
    as_user "$account" "$work/home-$account/.local/bin/niri-fx" --version \
        > "$output/retained-$account-after-removal-version.txt"
    cmp "$output/retained-$account-version.txt" "$output/retained-$account-after-removal-version.txt"
    snapshot "$work/home-$account" "$output/user-$account-removed.json"
    cmp "$output/user-$account-adopted.json" "$output/user-$account-removed.json"
done
snapshot niri "$output/niri-removed.json"
cmp "$output/niri-before.json" "$output/niri-removed.json"
printf '%s\n' 'PASS: audited archives, install, two-user reviewed adoption, retained CLI after removal, and unchanged stock Niri files.'
printf '%s\n' 'No compositor session was launched. Display-manager/systemd lifecycle, portals and physical desktop acceptance remain separate gates.'
