"""Summarize owned-session WAYLAND_DEBUG logs without exporting raw arguments.

These logs describe client requests and server receipt, not buffer contents,
successful rendering or presentation. Server sender IDs are connection-local
and do not carry a connection identity, so cross-process attribution is limited.
"""

import re
from pathlib import Path

# Rust wayland-backend uses @ and explicit <-; libwayland may use # and omits
# the arrow for received messages. Ignore every interface outside this list.
MESSAGE = re.compile(
    rb"^\[\s*(?:\d+:\d+:)?\d+\.\d+\](?:\[rs\])?\s*"
    rb"(?:\{[^}\r\n]*\}\s*)?(?P<direction>->|<-)?\s*"
    rb"(?P<interface>wl_surface|xdg_wm_base|xdg_surface)[@#](?P<id>\d+)\."
    rb"(?P<method>[a-z_]+),?\s*\((?P<arguments>[^\r\n]*)\)\s*$"
)
SURFACE_ARGUMENTS = re.compile(
    rb"(?:new id )?xdg_surface[@#](\d+)(?:\[\d+\])?,\s*"
    rb"wl_surface[@#](\d+)(?:\[\d+\])?"
)
METHODS = ("attach", "damage", "damage_buffer", "commit", "frame")
MAX_LOG_BYTES = 16 * 1024 * 1024


def counts(events, start, end, surface=None):
    """Count only allowlisted requests in a half-open byte range."""
    result = dict.fromkeys(METHODS, 0)
    for offset, sender, method in events:
        if start <= offset < end and (surface is None or sender == surface):
            result[method] += 1
    return result


def surface_trace(path: Path, direction: str, intervals: list[dict]):
    """Read a bounded log and report counters for controller-observed phases.

    Byte boundaries avoid comparing different log clocks, which can wrap. They
    are observations of log writes, not protocol dispatch timestamps. Unknown
    formats and ambiguous toplevel selection remain explicit in the report.
    """
    if direction not in ("sent", "received"):
        raise ValueError("Trace direction must be sent or received")
    result = {
        "direction": direction,
        "status": "unavailable",
        "connection_identity": "not present on surface request log lines",
        "boundary_basis": "log byte offsets sampled by the diagnostic controller",
        "proves_presentation": False,
    }
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_LOG_BYTES + 1)
    except OSError:
        return result | {"reason": "log unavailable"}
    if len(data) > MAX_LOG_BYTES:
        return result | {"reason": "log exceeds diagnostic size limit"}

    events = []
    mappings = []
    toplevels = []
    unparsed = 0
    offset = 0
    for line in data.splitlines(keepends=True):
        match = MESSAGE.fullmatch(line)
        if match:
            arrow = match["direction"]
            wanted = arrow == b"->" if direction == "sent" else arrow in (None, b"<-")
            if wanted:
                interface = match["interface"]
                method = match["method"].decode("ascii")
                sender = int(match["id"])
                if interface == b"wl_surface" and method in METHODS:
                    events.append((offset, sender, method))
                elif interface == b"xdg_wm_base" and method == "get_xdg_surface":
                    arguments = SURFACE_ARGUMENTS.fullmatch(match["arguments"])
                    mappings.append(tuple(map(int, arguments.groups())) if arguments else None)
                elif interface == b"xdg_surface" and method == "get_toplevel":
                    toplevels.append(sender)
        elif b"wl_surface" in line and any(
            b"." + method.encode("ascii") + b"(" in line
            or b"." + method.encode("ascii") + b"," in line
            for method in METHODS
        ):
            unparsed += 1
        offset += len(line)

    selected = None
    if len(mappings) == len(toplevels) == 1:
        mapping = mappings[0]
        if mapping is not None and mapping[0] == toplevels[0]:
            selected = mapping[1]
    traffic = counts(events, 0, len(data))
    # An observed commit is a positive control for log support. Zero activity
    # in an interval is useful only if this control has actually been seen.
    supported = traffic["commit"] > 0
    toplevel_traffic = counts(events, 0, len(data), selected) if selected is not None else None
    toplevel_supported = toplevel_traffic is not None and toplevel_traffic["commit"] > 0
    result.update(
        status="available"
        if supported and not unparsed
        else "limited"
        if supported
        else "unavailable",
        unparsed_surface_lines=unparsed,
        surface_commit_observed=supported,
        toplevel_commit_observed=toplevel_supported,
        surface_selection=(
            "single observed xdg_toplevel; connection identity unverified"
            if selected is not None
            else "unavailable or ambiguous"
        ),
        all_surface_requests=traffic if supported else None,
        toplevel_requests=toplevel_traffic if toplevel_supported else None,
        phases=[],
    )
    if not supported:
        result["reason"] = "no recognized surface commit; absence of traffic is not established"
    for interval in intervals:
        start, end = interval["start_offset"], interval["end_offset"]
        if not 0 <= start <= end <= len(data):
            raise ValueError("Trace interval is outside the observed log")
        result["phases"].append(
            {
                "phase": interval["phase"],
                "begin_ms_after_close": interval["begin_ms_after_close"],
                "end_ms_after_close": interval["end_ms_after_close"],
                "all_surface_requests": counts(events, start, end) if supported else None,
                "toplevel_requests": (
                    counts(events, start, end, selected) if toplevel_supported else None
                ),
            }
        )
    return result
