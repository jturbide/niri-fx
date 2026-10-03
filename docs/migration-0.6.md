# Moving from Niri Fragments to NiriFX

Version 0.6 adds the Slices family and renames the project to **NiriFX**. The
repository is `jturbide/niri-fx`, the application is **NiriFX Studio**, and the
distribution/primary executable are `niri-fx`. The Python entry point is
`python3 -m niri_fx`.

## What keeps working

- The `niri-fragments` executable and `python3 -m niri_fragments` remain aliases.
- Existing schema 1 JSON imports as Fragments, preserving explicit resize choices.
  Fragment exports stay schema 1 and remain readable by 0.5. Slice exports use
  schema 2; 0.5 cannot import them.
- iNiR IDs and ownership retain `niri-fragments-`, including custom IDs, so updates
  replace the same entries and preserve named styles. Display labels become NiriFX.
- Setup state remains in `~/.local/state/niri-fragments/setup`. Old snapshots,
  managed include markers and `fragments/niri-fragments.kdl` remain recognized.
- Studio keeps its existing profile and desktop-file identity. Existing launchers
  keep working and may retain the old visible name; setup preserves them.
- All 14 fragment presets keep their exact 0.5 shader source. Resize remains off
  by default. Slices currently supports opening and closing only.

## Source checkout

Update the remote and pull after reviewing your local changes:

```sh
git remote set-url origin git@github.com:jturbide/niri-fx.git
git pull --ff-only
python3 -m niri_fx --version
python3 -m niri_fx studio
```

An existing checkout directory can keep its old name. This also preserves
launchers tied to that directory. GitHub redirects the old repository URL; do
not create another repository named `niri-fragments`, which would replace that
redirect. See [GitHub's rename behavior](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

## Installed Python package

Use a fresh virtual environment, or uninstall the old distribution **before**
installing the renamed one in the same environment:

```sh
.venv/bin/python -m pip uninstall niri-fragments
.venv/bin/python -m pip install .
.venv/bin/niri-fx --version
.venv/bin/niri-fragments --version
```

The distributions share the legacy module and executable, so leaving both
installed can make a later uninstall remove files used by the other package.
Neither step removes your user presets or setup snapshots. There is no official
PyPI or AUR publication; install from the checkout or GitHub release wheel.

## Activate the new presets

For iNiR, register the pack and select the desired style in iRiS:

```sh
python3 -m niri_fx register --dry-run
python3 -m niri_fx register
```

If your active preset is unrecognized, supply the same explicit `--base` you
previously used. Registration does not activate a style. Existing custom entries
remain in the registry. For standalone Niri, preview `setup --preset slide-apart`
and repeat with `--apply` only after reviewing its target/paths, or use your
existing manual include workflow.

Slices does not inherit fragment physics. Studio shows only the selected family's
controls; incompatible CLI options and unsupported slice resize/movement requests
fail explicitly. `niri-fx families` lists renderer capabilities; movement support
for Fragments still requires the separate experimental patched compositor.

## Development after 0.6

The implementation and resources now live in `niri_fx`. Legacy Python submodules
are aliases of the same module objects, including monkeypatch behavior, rather
than duplicated implementations. Fresh launcher commands use `niri_fx`; stable
launcher/profile/state identities are deliberately retained.

New waves/variation and Elastic presets use schema 3. Legacy-only exports retain
schema 1/2. Slide Apart now alternates adjacent strips; Split Curtain preserves
the former outward split. Existing saved slice documents keep their own direction.
See [new controls](effect-controls.md) and [Noctalia setup](noctalia.md).
