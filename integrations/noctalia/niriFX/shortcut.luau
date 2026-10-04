--!nonstrict
-- SPDX-License-Identifier: MIT
-- The shared app owns browsing, editing and reviewed activation. Argument arrays
-- keep configured paths literal and avoid a second shell/configuration backend.
shortcut.setLabel("NiriFX")
shortcut.setIcon("movie")
shortcut.setActive(false)
shortcut.setEnabled(true)

function onClick()
  noctalia.runAsync({
    "niri-fx", "studio", "--target", "noctalia", "--active",
    "--preset-dir", noctalia.getConfig("presets_dir") or "~/.config/niri/nirifx-presets",
    "--picker-file", noctalia.getConfig("target_file") or "~/.config/niri/animations.kdl",
  })
end
