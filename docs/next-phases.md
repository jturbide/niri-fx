# Development design notes

These notes explain the technical questions behind the [project roadmap](../ROADMAP.md).
They are a starting point for contributors, not a list of required steps for using NiriFX.

## Rendering and interruptions

A window effect has more state than its visible position: texture geometry,
progress, seed, rotation and direction all contribute to a continuous image.
Retargeting should retain those values where possible. A new random field or a
fully reconstructed snapshot can produce a visible jump even when position is continuous.

The experimental patch carries shader phase through swaps, blends direction
impulses and continues an interrupted opening trajectory while fading out. This
preserves visual state and sampled deformation speed through cubic handoffs.
Interrupted tile and column offsets also retain their sampled position velocity
when a movement shader is configured. Their cubic path ends at the new destination
with zero speed; unchanged moves use Niri's configured curve. Acceleration,
camera motion and shared particle physics remain separate problems. Phase curves
must stay bounded without discarding their incoming speed.

Changes to this path should include deterministic state tests and native recordings
of reversal, repeated retargets, close-during-open, close-during-move and shader
removal. Verify the final layout and disappearance of closed surfaces. Retain
Niri's blocked-out capture paths and ordinary-renderer fallback.

## Performance evidence

Use [the GPU harness](performance.md) for shader draw cost. Measure compositor
presentation separately: capture cadence, IPC acknowledgements and WebGL GPU
queries answer different questions. Record the driver, window/output dimensions,
refresh rate, sample count and release/debug build profile with each result.

Inverse shader lookups need a coverage bound before reducing their search radius.
Compare intermediate frames, extreme settings and multiple seeds against a
reference renderer. Preserve premultiplied alpha, transparent decorations and
exact endpoints. Particle count alone is not a universal performance control.

## Shell integration contract

Reuse the parameter catalog and CLI rather than reproducing shader math in a
picker. A shell adapter should provide search, editable profiles, deliberate
activation, a dedicated restore state and visible error messages. Use argument
arrays and catalog identifiers instead of interpolating names into shell commands.

Test selection, activation and exact restore with temporary configurations. Keep
resize opt-in, preserve unrelated settings, and describe ownership when another
animation manager is present. See [integration priorities](roadmap.md).

## Adding effects and controls

Follow [Adding an effect](adding-effects.md) and [Architecture](architecture.md).
Each distinct effect needs an importable example, a faithful recording and
Python/browser export parity. Family capability metadata determines which actions
are supported; supporting resize never enables it automatically.

Basic Studio controls should be enough to tune the main look. Detailed controls
belong in Advanced view and must retain their values when hidden. Respect reduced
motion in previews and galleries without silently changing exported effects.
