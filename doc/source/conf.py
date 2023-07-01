"""Configuration file for sphinx documentation."""
# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import sys
from pathlib import Path
from sphinx.ext import apidoc

sys.path.insert(0, str(Path.cwd().absolute()))

import qibosoq

# -- Project information -----------------------------------------------------

project = "Qibosoq"
copyright = "2023, The Qibo team"
author = "The Qibo team"

release = qibosoq.__version__

# -- General configuration ---------------------------------------------------

# https://stackoverflow.com/questions/56336234/build-fail-sphinx-error-contents-rst-not-found
# master_doc = "index"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "recommonmark",
    "sphinx_copybutton",
    "sphinx_last_updated_by_git",
    "sphinx.ext.viewcode",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"

# custom title
html_title = "Version " + release

# custom html theme options (colors and font)

html_theme_options = {
    "top_of_page_button": "edit",
    "source_repository": "https://github.com/qiboteam/qibosoq/",
    "source_branch": "main",
    "source_directory": "doc/source/",
    "light_css_variables": {
        "color-brand-primary": "#6400FF",
        "color-brand-secondary": "#6400FF",
        "color-brand-content": "#6400FF",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/qiboteam/qibosoq",
            "html": """
                    <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                        <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                    </svg>
                """,
            "class": "",
        },
    ],
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

autodoc_mock_imports = ["qick", "qick.QickSoc"]


def run_apidoc(_):
    source = Path(__file__).parent
    docs_dest = source / "api-reference"
    package = source.parents[1] / "src" / "qibosoq"
    apidoc.main(["--module-first", "-o", str(docs_dest), str(package)])


def setup(app):
    """Include custom style to change colors."""
    app.add_css_file("css/style.css")
    app.connect("builder-inited", run_apidoc)
