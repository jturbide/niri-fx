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


def json_subset(actual, expected):
    """Select only reference fields; additional discovery/output fields are allowed."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        return {key: json_subset(actual[key], value) for key, value in expected.items()}
    if isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected)
        return [
            json_subset(value, reference) for value, reference in zip(actual, expected, strict=True)
        ]
    if type(expected) in (int, float):
        assert type(actual) in (int, float), "A numeric response field must remain numeric"
    else:
        assert type(actual) is type(expected), "A response field changed JSON type"
    return actual


def stock_action_contract(kdl):
    """Read action semantics, leaving shader bytes and KDL layout out of the corpus."""
    from niri_fx.setup import _kdl_nodes

    ((name, _, nodes),) = _kdl_nodes(kdl.encode())
    assert name == "animations"
    actions = {}
    for name, _, children in nodes:
        fields = {key: values for key, values, _ in children}
        if "off" in fields:
            assert set(fields) == {"off"}, "Off must not carry a shader or timing override"
            actions[name] = {"off": True}
        else:
            actions[name] = {
                "duration_ms": int(fields["duration-ms"][0]),
                "shader": bool(fields["custom-shader"]),
            }
    return actions
