"""Command line interface entry points for VPrism."""

from .main import app, create_app, bootstrap_plugins

__all__ = ["app", "create_app", "bootstrap_plugins"]
