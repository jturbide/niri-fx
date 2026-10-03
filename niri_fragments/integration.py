"""Compatibility alias for :mod:`niri_fx.integration`."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("niri_fx.integration")
