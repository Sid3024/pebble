"""
Package entry point -- allows running the FlowerGame with ``python -m FlowerGame``.

This file simply imports and calls the CLI function from main.py.  All actual
argument parsing and async bootstrapping lives there.
"""

from .main import cli

cli()
