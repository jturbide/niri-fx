# Pick a preset from your terminal

NiriFX is one command-line tool with optional graphical interfaces. For everyday
use, pick a finished preset and apply it; opening an editor is optional. The
terminal guide needs Python and Niri, with no additional UI toolkit or daemon.

From the checkout:

```sh
python3 -m niri_fx
```

After [installing](getting-started.md), run `niri-fx`. It starts the guide when
input and output are terminals; redirected output prints help without prompting.
Use `niri-fx setup --interactive` for an explicit interactive invocation.

![Choose Fragment Flow, review, apply and undo in the terminal](gifs/workflow-terminal.gif)

## Choose, review, apply

On standalone Niri, the guide starts with nine recommended presets. Enter a
number or preset name, use `profiles` for seven open/close pairings, `all` for all
64 single styles and seven profiles, or search with `/slices`,
`/wobble` or `/pixel`. An empty selection chooses Balanced. `q` leaves the guide.

For an everyday starting point, try Balanced. Spring Wobble, Pixel Wipe and
Shockwave offer distinct looks with low measured shader costs on the tested GPU.
Core Detonation is a heavier spectacle; see the [performance comparisons](performance.md)
when choosing effects for large windows or frequent animations.

The review lists the files to create or update. Type **apply** to write those
changes; Enter cancels. Apply rebuilds and verifies the reviewed plan, so external
edits while the prompt is open require a fresh review. It activates the selected
opening/closing effect through Niri's normal config reload.

Built-ins use your base resize behavior; no built-in enables a resize shader.
Replacing an earlier NiriFX resize override with a built-in removes that override
and exposes the base settings. The guide adds no Studio launcher by default.

On **iNiR**, automatic detection offers to register the built-in collection.
Then choose the style in **iRiS Settings → Windows → Movement → Style**.
Registration does not activate an effect or rewrite your current animation file.

Use one owner for animation settings. An explicit standalone include overrides
earlier shell-managed effects. [DMS](dms.md) and [Noctalia](noctalia.md) users can
keep their existing pickers and use their dedicated setup guides.

## Undo or use a different config

Run the guide again, type `undo`, review the listed files and confirm with
**undo**. This uses the same history as ordinary CLI setup:
`$XDG_STATE_HOME/niri-fx/setup`, falling back to `~/.local/state/niri-fx/setup`.
The graphical pickers have separate histories, documented in their guides.

```sh
niri-fx setup --interactive --target standalone --config /path/to/config.kdl --state /path/to/history
niri-fx restore --state /path/to/history
niri-fx restore --state /path/to/history --apply
```

Use the same config/state options when returning to a nonstandard setup.
Undo restores exact prior file bytes and refuses external edits. With iNiR,
choose a previous non-NiriFX style first: restoring the registry does not change
the shader already selected by the shell. See [setup and restore](setup.md).

EOF or Ctrl+C exits the guide. Already completed changes remain in history.
Interactive mode refuses piped input and automatic `--apply`; scripts should use
the ordinary JSON setup/restore commands.

## Browse and diagnose without prompts

```sh
niri-fx list --text --recommended
niri-fx list --profiles --text
niri-fx list --text --family slices
niri-fx list --text --search pixel
niri-fx doctor --text
```

Plain `list` and `doctor` retain JSON output for integrations. Filters also work
with JSON. The diagnostic report checks Niri/config health and optional picker
dependencies. Missing Quickshell or GJS/GTK does not make a core installation
unhealthy. Install a toolkit only if you want that graphical interface.

For visual comparisons, use the [gallery](https://jturbide.github.io/niri-fx/gallery/).
For custom parameters or editing independent action profiles, use [Studio](usage.md)
or [scriptable setup](setup.md). The terminal guide selects the same styles and profiles as
the catalog; it does not maintain a separate effect library.
