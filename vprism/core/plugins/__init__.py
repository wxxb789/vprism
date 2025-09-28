"""Plugin framework for the VPrism CLI."""

from .loader import PluginLoader, PluginLoadResult

__all__ = ["PluginLoader", "PluginLoadResult"]
