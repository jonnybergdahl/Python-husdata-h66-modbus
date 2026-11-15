# Configuration file for the Sphinx documentation builder.

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

with (ROOT / "pyproject.toml").open("rb") as f:
    release = tomllib.load(f)["project"]["version"]

project = "husdata-h66-modbus"
copyright = "2026, Jonny Bergdahl"
author = "Jonny Bergdahl"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # supports :param: style
    "sphinx_autodoc_typehints",  # renders type hints nicely
]

autodoc_member_order = "bysource"

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
