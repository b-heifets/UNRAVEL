#!/usr/bin/env python3

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import SimpleITK as sitk
import pathlib

from abc_atlas_access.abc_atlas_cache.abc_project_cache import AbcProjectCache

# Update the base download directory to your local path
download_base = pathlib.Path('/Users/Danielthy/Documents/_Heifets_lab_data/_UNRAVEL/ABC_atlas/abc_download_root')
abc_cache = AbcProjectCache.from_s3_cache(download_base) # Initialize the cache
print(abc_cache.current_manifest)

# Read in cell metadata and rename columns for section coordinates
cell = abc_cache.get_metadata_dataframe(directory='MERFISH-C57BL6J-638850-CCF', file_name='cell_metadata_with_cluster_annotation')

cell.rename(columns={'x': 'x_section',
                     'y': 'y_section',
                     'z': 'z_section'},
            inplace=True)
cell.set_index('cell_label', inplace=True)

# Read in the reconstructed coordinates and join them with the cell dataframe
reconstructed_coords = abc_cache.get_metadata_dataframe(
    directory='MERFISH-C57BL6J-638850-CCF',
    file_name='reconstructed_coordinates',
    dtype={"cell_label": str}
)
reconstructed_coords.rename(columns={'x': 'x_reconstructed',
                                     'y': 'y_reconstructed',
                                     'z': 'z_reconstructed'},
                            inplace=True)
reconstructed_coords.set_index('cell_label', inplace=True)

cell_joined = cell.join(reconstructed_coords, how='inner')

# Repeat the process for the cell CCF coordinates
ccf_coords = abc_cache.get_metadata_dataframe(
    directory='MERFISH-C57BL6J-638850-CCF',
    file_name='ccf_coordinates',
    dtype={"cell_label": str}
)
ccf_coords.rename(columns={'x': 'x_ccf',
                           'y': 'y_ccf',
                           'z': 'z_ccf'},
                  inplace=True)
ccf_coords.set_index('cell_label', inplace=True)

cell_joined = cell_joined.join(ccf_coords, how='inner')

# Visualization helper function
def plot_section(xx=None, yy=None, cc=None, val=None, pcmap=None, 
                 overlay=None, extent=None, bcmap=plt.cm.Greys_r, alpha=1.0,
                 fig_width = 6, fig_height = 6):
    
    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)

    if xx is not None and yy is not None and pcmap is not None:
        plt.scatter(xx, yy, s=0.5, c=val, marker='.', cmap=pcmap)
    elif xx is not None and yy is not None and cc is not None:
        plt.scatter(xx, yy, s=0.5, color=cc, marker='.', zorder=1)   
        
    if overlay is not None and extent is not None and bcmap is not None:
        plt.imshow(overlay, cmap=bcmap, extent=extent, alpha=alpha, zorder=2)
        
    ax.set_ylim(11, 0)
    ax.set_xlim(0, 11)
    ax.axis('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    
    return fig, ax

# Visualize cells in a specific section
brain_section = 'C57BL6J-638850.40'
pred = (cell_joined['brain_section_label'] == brain_section)
section = cell_joined[pred]

fig, ax = plot_section(xx=section['x_section'],
                       yy=section['y_section'], 
                       cc=section['neurotransmitter_color'])
res = ax.set_title("Neurotransmitter - Section Coordinates")

fig, ax = plot_section(xx=section['x_reconstructed'],
                       yy=section['y_reconstructed'], 
                       cc=section['neurotransmitter_color'])
res = ax.set_title("Neurotransmitter - Reconstructed Coordinates")
