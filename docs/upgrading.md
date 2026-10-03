# Updating the development checkout

NiriFX is an early project with one current API. Development changes may remove
old interfaces; compatibility shims are not maintained. Read the [changelog](../CHANGELOG.md)
before updating. Tagged releases retain their own documentation.

The current interface is `niri-fx` or `python3 -m niri_fx`. Preset JSON uses
**schema 3** for every family. [Independent action profiles](profiles.md) use a
separate document type, kind `profile`, schema 1. Namespaced state lives under
`$XDG_STATE_HOME/niri-fx`; desktop launchers are `niri-fx-studio.desktop` and
`niri-fx-movement-demo.desktop`. The iNiR registry uses the `niri-fx` generator
and ID prefix. Standalone setup owns `nirifx/animations.kdl`.

Update a clean checkout with `git pull --ff-only`, and reinstall into a fresh
virtual environment when testing an installed package. Re-export or recreate
presets from unsupported formats. Old Python modules and command aliases are
not installed. An old distribution in the same environment should be uninstalled
before installing NiriFX.

Back up local settings before replacing old registrations or launchers. Select a
base shell style, remove old project-owned entries, register the current pack,
and select the new style. Keep personal custom values and explicit resize choices.
Historical snapshots remain recovery evidence; do not rewrite them into new
formats or delete them during an update.

Resize is opt-in. Registration does not activate effects. Read [setup and restore](setup.md)
and [iNiR integration](integration.md) for current paths and ownership boundaries.

Single-style JSON now requires exactly `schema`, `name` and `effect`, matching the
strict outer-field validation already used for profiles. Remove unrelated metadata
from preset files. Unknown effect parameters and malformed names remain errors.
The maintenance refactor changes internal Python module locations; the `niri-fx`
CLI, document schemas and existing presets remain the supported user interfaces.
