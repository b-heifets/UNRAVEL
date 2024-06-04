# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath('..'))

# Print the sys.path for debugging purposes
print("Modified sys.path:", sys.path)

sys.path.append('../atlas_tools')
sys.path.append('../cluster_correction')
sys.path.append('../cluster_validation')
sys.path.append('../cluster_validation/effect_sizes')
sys.path.append('../image_io')
sys.path.append('../image_tools')
sys.path.append('../region_stats')
sys.path.append('../registration')
sys.path.append('../segmentation')
sys.path.append('../unravel')
sys.path.append('../utilities')
sys.path.append('../voxel_stats')
sys.path.append('../warp')


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
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages'
]


templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']
