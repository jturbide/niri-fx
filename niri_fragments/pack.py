"""Compatibility alias for :mod:`niri_fx.pack`."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("niri_fx.pack")
