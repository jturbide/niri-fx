#!/usr/bin/env bash
# Reuse package adoption acceptance, adding bounded dependency fault probes.
set -euo pipefail

if [[ ${NIRIFX_ARCH_PACKAGE_CONTAINER:-} != 1 ]] ||
    [[ ! -f /.dockerenv && ! -f /run/.containerenv ]]; then
    printf '%s\n' 'Refusing host execution: use a disposable container with NIRIFX_ARCH_PACKAGE_CONTAINER=1.' >&2
    exit 2
fi
if [[ $EUID != 0 || $# != 2 ]]; then
    printf '%s\n' 'Usage as container root: test-arch-session-dependencies.sh OUTPUT PACKAGE_ARCHIVE' >&2
    exit 2
fi
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export NIRIFX_ARCH_SESSION_DEPENDENCIES=1
exec bash "$repo/scripts/test-arch-session-package.sh" "$@"
