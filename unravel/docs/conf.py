# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

print(sys.executable)

sys.path.insert(0, os.path.abspath('..'))

print(sys.path)

sys.path.append(os.path.abspath('../cluster_stats'))
sys.path.append(os.path.abspath('../cluster_stats/effect_sizes'))
sys.path.append(os.path.abspath('../image_io'))
sys.path.append(os.path.abspath('../image_tools'))
sys.path.append(os.path.abspath('../image_tools/atlas'))
sys.path.append(os.path.abspath('../region_stats'))
sys.path.append(os.path.abspath('../register'))
sys.path.append(os.path.abspath('../segment'))
sys.path.append(os.path.abspath('../unravel'))
sys.path.append(os.path.abspath('../utilities'))
sys.path.append(os.path.abspath('../voxel_stats'))
sys.path.append(os.path.abspath('../warp'))

print(sys.path)


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'UNRAVEL'
copyright = '2024, Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets'
author = 'Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets'
release = '1.0.0-beta'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages', 
    'sphinx.ext.todo'
]


templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']
