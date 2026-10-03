"""Synthetic fixtures shared by tests; never read an installed desktop config."""


def shell_registry():
    return {
        "active": "example",
        "presets": [
            {
                "id": "example",
                "types": {
                    "workspace-switch": {"spring": [0.9, 700, 0.0001]},
                    "window-resize": {
                        "duration-ms": 210,
                        "curve": "ease-out-cubic",
                        "custom-shader": "existing resize shader",
                    },
                    "window-open": {"duration-ms": 170, "curve": "ease-out-expo"},
                    "window-close": {"duration-ms": 130, "curve": "ease-out-quad"},
                },
            }
        ],
    }
