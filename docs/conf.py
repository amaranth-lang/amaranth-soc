import os, sys
sys.path.insert(0, os.path.abspath("."))

import time
import amaranth_soc

project = "System on Chip toolkit for Amaranth HDL"
version = amaranth_soc.__version__.replace(".editable", "")
release = version.split("+")[0]
copyright = time.strftime("2020—%Y, Amaranth project contributors")

extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.doctest",
    "sphinx.ext.todo",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
    "sphinxcontrib.yowasp_wavedrom",
]

with open(".gitignore") as f:
    exclude_patterns = [line.strip() for line in f.readlines()]

root_doc = "cover"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "amaranth": ("https://amaranth-lang.org/docs/amaranth/latest", None),
}

todo_include_todos = True

autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True
}
autodoc_preserve_defaults = True

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_ivar = True
napoleon_include_init_with_doc = True
napoleon_include_special_with_doc = True
napoleon_custom_sections = [
    ("Arguments", "params_style"), # by default displays as "Parameters"
    ("Attributes", "params_style"), # by default displays as "Variables", which is confusing
    ("Members", "params_style"), # `amaranth.lib.wiring` signature members
]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "_static/logo.png"

rst_prolog = """
.. role:: py(code)
   :language: python
"""
