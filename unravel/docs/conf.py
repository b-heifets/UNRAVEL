# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime
import os
import sys

sys.path.insert(0, os.path.abspath('../..'))

sys.path.insert(1, os.path.abspath('..'))
# sys.path.insert(0, os.path.abspath('..'))
sys.path.append(os.path.abspath('../cluster_stats'))
sys.path.append(os.path.abspath('../cluster_stats/effect_sizes'))
sys.path.append(os.path.abspath('../core'))
sys.path.append(os.path.abspath('../image_io'))
sys.path.append(os.path.abspath('../image_tools'))
sys.path.append(os.path.abspath('../image_tools/atlas'))
sys.path.append(os.path.abspath('../region_stats'))
sys.path.append(os.path.abspath('../register'))
sys.path.append(os.path.abspath('../segment'))
sys.path.append(os.path.abspath('../utilities'))
sys.path.append(os.path.abspath('../voxel_stats'))
sys.path.append(os.path.abspath('../warp'))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'UNRAVEL'
current_year = datetime.datetime.now().year
copyright = f'{current_year}, the UNRAVEL team'
author = 'Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets'
release = '1.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx.ext.todo',
    'sphinx_togglebutton',
    'sphinx.ext.intersphinx', 
    'sphinx_design', 
    'sphinxcontrib.mermaid'
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}

autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
}
autodoc_member_order = 'bysource'
autodoc_inherit_docstrings = True
autodoc_typehints = 'description'

myst_enable_extensions = [
    "colon_fence"
]

suppress_warnings = [
    'myst.xref_ambiguous',  # Suppresses ambiguous reference warnings from MyST-parser
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

todo_include_todos = True


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}
master_doc = 'index'

html_context = {
   "default_mode": "dark"
}

html_theme_options = {
    "navbar_end": ["navbar-icon-links"],  # Omit `theme-switcher` to disable light mode
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/b-heifets/UNRAVEL",
            "icon": "fab fa-github-square",
            "type": "fontawesome",
        }
    ],
}
html_title = "UNRAVEL docs"


# Add custom CSS
html_static_path = ['_static']
html_favicon = '_static/favicon.png'
html_css_files = [
    'custom.css',
]

# Generate anchors for headings up to h3
myst_heading_anchors = 3  
