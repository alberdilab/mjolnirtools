"""Sphinx configuration for mjolnirtools documentation."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from mjolnirtools import __version__  # noqa: E402


project = "mjolnirtools"
author = "Mjolnir HPC administrators"
copyright = "2026, Mjolnir HPC administrators"

version = __version__
release = __version__

extensions = [
    "sphinx.ext.autodoc",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 2,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": True,
}
html_static_path = ["_static"]
html_title = f"mjolnirtools {release}"

autodoc_typehints = "description"
