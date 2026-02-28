"""Command line interface entry points for VPrism."""

from .main import app, bootstrap_plugins, create_app

__all__ = ["app", "create_app", "bootstrap_plugins"]
