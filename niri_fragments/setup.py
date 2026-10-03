"""Compatibility alias for :mod:`niri_fx.setup`."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("niri_fx.setup")
