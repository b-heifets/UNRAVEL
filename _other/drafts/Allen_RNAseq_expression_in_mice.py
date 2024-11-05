#!/usr/bin/env python3

"""
Use ``./Allen_RNAseq_expression`` from UNRAVEL to extract expression data for specific genes from the Allen Brain Cell Atlas RNA-seq data.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.htmlml

Usage:
------
    ./Allen_RNAseq_expression -b path/base_dir -g genes [-s mouse | human] [-c Neurons | Nonneurons] [-r region] [-d log2 | raw ] [-o output] [-v]

Usage for mice:
---------------
    ./Allen_RNAseq_expression -b path/base_dir -g genes -r region [-o output_dir] [-v]
"""

from pathlib import Path
from matplotlib import pyplot as plt
import pandas as pd
from rich import print
from rich.traceback import install

import merfish as m
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the MERFISH data', required=True, action=SM)
    # reqs.add_argument('-i', '--input', help='path/gene_expression.csv', required=True, action=SM)
    # reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def load_RNAseq_mouse_cell_metadata(download_base):
    cell_df = None

    cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
    if cell_metadata_path.exists():
        print(f"\n    Loading cell metadata from {cell_metadata_path}\n")
        cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str}, 
                                usecols=['cell_label', 'region_of_interest_acronym', 'dataset_label', 'x', 'y', 'cluster_alias'])
        
    if cell_df is not None:
        cell_df.set_index('cell_label', inplace=True)
    else:
        print(f"\n    [red1]Cell metadata not loadable from: {cell_metadata_path}\n")
        import sys ; sys.exit()
    return cell_df

def join_region_of_interest_metadata(cell_df, download_base):
    roi_df = None
    roi_metadata_path = download_base / "metadata/WMB-10X/20231215/region_of_interest_metadata.csv"
    if roi_metadata_path.exists():
        print(f"\n    Loading region of interest metadata from {roi_metadata_path}\n")
        roi_df = pd.read_csv(roi_metadata_path, dtype={'acronym': str})
        
    if roi_df is not None:
        roi_df.set_index('acronym', inplace=True)
        roi_df.rename(columns={'order': 'region_of_interest_order',
                    'color_hex_triplet': 'region_of_interest_color'}, inplace=True)
        cell_df_joined = cell_df.join(roi_df[['region_of_interest_order', 'region_of_interest_color']], on='region_of_interest_acronym')
        
    else:
        print(f"\n    [red1]Region of interest metadata not loadable from: {roi_metadata_path}\n")
        import sys ; sys.exit()
    return cell_df_joined

def plot_umap(xx, yy, cc=None, val=None, fig_width=8, fig_height=8, cmap=None):

    fig, ax = plt.subplots()
    fig.set_size_inches(fig_width, fig_height)
    
    if cmap is not None :
        plt.scatter(xx, yy, s=0.5, c=val, marker='.', cmap=cmap)
    elif cc is not None :
        plt.scatter(xx, yy, s=0.5, color=cc, marker='.')
        
    ax.axis('equal')
    ax.set_xlim(-18, 27)
    ax.set_ylim(-18, 27)
    ax.set_xticks([])
    ax.set_yticks([])
    
    return fig, ax

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    cell_df = load_RNAseq_mouse_cell_metadata(download_base) 

    cell_df_joined = m.join_cluster_details(cell_df, download_base)

    cell_df_joined = m.join_cluster_colors(cell_df_joined, download_base)

    cell_df_joined = join_region_of_interest_metadata(cell_df_joined, download_base)

    cell_subsampled = cell_df_joined.loc[::10]

    # Plot the UMAP
    fig, ax = plot_umap(cell_subsampled['x'], cell_subsampled['y'], cc=cell_subsampled['neurotransmitter_color'])
    res = ax.set_title("Neuortransmitter Identity")
    plt.show()

    verbose_end_msg()

if __name__ == '__main__':
    main()