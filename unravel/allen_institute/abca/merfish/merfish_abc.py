#!/usr/bin/env python3
"""
Use ``merfish_abc.py`` from UNRAVEL to plot MERFISH data with layered visualizations (adapted by Austen Casey from the merfish module).

Layers when using -c (color mode):
    - All cells (from the base metadata) are shown at low opacity
    - A subset of cells (from your metadata file) are over-plotted at full opacity
    - The annotation boundary overlay (wireframe) is added on top.
    
Layers when using -g (gene mode):
    - All cells are shown as a scatter plot where each cell is colored by its expression value for the chosen gene.
    - A colorbar is added.
    - The subset cells (e.g. neurons) are over-plotted with larger markers and full opacity.
    - The annotation boundary overlay is added on top.

Usage for gene:
---------------
    merfish_abc.py -b path/to/base_dir -s slice -g gene

Usage for color:
----------------
    merfish_abc.py -b path/to/base_dir -s slice -c color
"""

import anndata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import SimpleITK as sitk
from pathlib import Path
from rich import print
from rich.traceback import install
import nibabel as nib

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

# Import functions for expression data from your merfish module.
import merfish as m

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-s', '--slice', help='The brain slice to view (e.g., 40)', type=int, required=True, action=SM)
    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-g', '--gene', help='Gene to plot. In gene mode, each cell is colored by its expression.', action=SM)
    opts.add_argument('-c', '--color', help='Metadata color to plot (e.g., parcellation_substructure_color or neurotransmitter_color)', action=SM)
    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


def load_cell_metadata(metadata_file):
    print(f"\n    Loading cell metadata from {metadata_file}\n")
    cell_df = pd.read_csv(metadata_file, dtype={'cell_label': str})
    cell_df.rename(columns={'x': 'x_section',
                            'y': 'y_section',
                            'z': 'z_section'},
                    inplace=True)
    cell_df.set_index('cell_label', inplace=True)
    return cell_df


def join_reconstructed_coords(cell_df, download_base):
    required_cols = {'x_reconstructed', 'y_reconstructed', 'z_reconstructed', 'parcellation_index'}
    if required_cols.issubset(cell_df.columns):
        print("\n    Reconstructed coordinates already present; skipping join.\n")
        return cell_df
    reconstructed_coords_path = download_base / 'metadata/MERFISH-C57BL6J-638850-CCF/20231215/reconstructed_coordinates.csv'
    print(f"\n    Adding reconstructed coordinates from {reconstructed_coords_path}\n")
    reconstructed_coords_df = pd.read_csv(reconstructed_coords_path, dtype={'cell_label': str})
    reconstructed_coords_df.rename(columns={
        'x': 'x_reconstructed', 
        'y': 'y_reconstructed', 
        'z': 'z_reconstructed'
    }, inplace=True)
    reconstructed_coords_df.set_index('cell_label', inplace=True)
    cell_df_joined = cell_df.join(reconstructed_coords_df, how='inner')
    return cell_df_joined


def join_cluster_details(cell_df_joined, download_base):
    cluster_details_path = download_base / 'metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_pivoted.csv'
    print(f"\n    Adding cluster details from {cluster_details_path}\n")
    cluster_details = pd.read_csv(cluster_details_path)
    cluster_details.set_index('cluster_alias', inplace=True)
    expected_cols = {'neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'}
    if expected_cols.issubset(cell_df_joined.columns):
        print("    Cluster details already present; skipping join.")
        return cell_df_joined
    cell_df_joined = cell_df_joined.join(cluster_details, on='cluster_alias')
    return cell_df_joined


def join_cluster_colors(cell_df_joined, download_base):
    cluster_colors_path = download_base / 'metadata/WMB-taxonomy/20231215/views/cluster_to_cluster_annotation_membership_color.csv'
    print(f"\n    Adding cluster colors from {cluster_colors_path}\n")
    cluster_colors = pd.read_csv(cluster_colors_path)
    cluster_colors.set_index('cluster_alias', inplace=True)
    expected_cols = {'neurotransmitter_color', 'class_color', 'subclass_color', 'supertype_color', 'cluster_color'}
    if expected_cols.issubset(cell_df_joined.columns):
        print("    Cluster colors already present; skipping join.")
        return cell_df_joined
    cell_df_joined = cell_df_joined.join(cluster_colors, on='cluster_alias')
    return cell_df_joined


def join_parcellation_annotation(cell_df_joined, download_base):
    parcellation_annotation_path = download_base / 'metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_acronym.csv'
    print(f"\n    Adding parcellation annotation from {parcellation_annotation_path}\n")
    parcellation_annotation = pd.read_csv(parcellation_annotation_path)
    parcellation_annotation.set_index('parcellation_index', inplace=True)
    expected_cols = {'parcellation_organ', 'parcellation_category', 'parcellation_division', 
                     'parcellation_structure', 'parcellation_substructure'}
    if expected_cols.issubset(cell_df_joined.columns):
        print("    Parcellation annotation already present; skipping join.")
        return cell_df_joined
    parcellation_annotation.columns = ['parcellation_%s' % x for x in parcellation_annotation.columns]
    cell_df_joined = cell_df_joined.join(parcellation_annotation, on='parcellation_index')
    return cell_df_joined


def join_parcellation_color(cell_df_joined, download_base):
    parcellation_color_path = download_base / 'metadata/Allen-CCF-2020/20230630/views/parcellation_to_parcellation_term_membership_color.csv'
    print(f"\n    Adding parcellation color from {parcellation_color_path}\n")
    parcellation_color = pd.read_csv(parcellation_color_path)
    parcellation_color.set_index('parcellation_index', inplace=True)
    expected_cols = {'parcellation_organ_color', 'parcellation_category_color',
                     'parcellation_division_color', 'parcellation_structure_color',
                     'parcellation_substructure_color'}
    if expected_cols.issubset(cell_df_joined.columns):
        print("    Parcellation color already present; skipping join.")
        return cell_df_joined
    parcellation_color.columns = ['parcellation_%s' % x for x in parcellation_color.columns]
    cell_df_joined = cell_df_joined.join(parcellation_color, on='parcellation_index')
    return cell_df_joined


def filter_brain_section(cell_df, slice_index):
    brain_section = f'C57BL6J-638850.{slice_index}'
    section = cell_df[cell_df['brain_section_label'] == brain_section]
    return section


def load_region_boundaries(download_base):
    annotation_boundary_image_path = download_base / 'image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation_boundary.nii.gz'
    print(f"\n    Loading annotation boundary image from {annotation_boundary_image_path}\n")
    annotation_boundary_image = sitk.ReadImage(str(annotation_boundary_image_path))
    annotation_boundary_array = sitk.GetArrayFromImage(annotation_boundary_image)
    size = annotation_boundary_image.GetSize()
    spacing = annotation_boundary_image.GetSpacing()
    extent = (-0.5 * spacing[0], (size[0] - 0.5) * spacing[0],
              (size[1] - 0.5) * spacing[1], -0.5 * spacing[1])
    return annotation_boundary_array, extent


def load_whole_ccf_image():
    image_path = Path('/SSD3/Austen/mdma_saline_social_60um_z_LR_avg_vox_p_tstat1_q0.05_rev_cluster_index_whole_cluster_7_MERFISH-CCF.nii.gz')
    print(f"\n    Loading whole MERFISH-CCF image from {image_path}\n")
    image = sitk.ReadImage(str(image_path))
    image_array = sitk.GetArrayFromImage(image)
    size = image.GetSize()
    spacing = image.GetSpacing()
    extent = (-0.5 * spacing[0], (size[0] - 0.5) * spacing[0],
              (size[1] - 0.5) * spacing[1], -0.5 * spacing[1])
    return image_array, extent


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Determine the z-index for the selected slice using a predefined mapping.
    brain_section_label = f'C57BL6J-638850.{args.slice}'
    slice_index_map = {
        "C57BL6J-638850.05": 4,
        "C57BL6J-638850.06": 5,
        "C57BL6J-638850.08": 7,
        "C57BL6J-638850.09": 8,
        "C57BL6J-638850.10": 9,
        "C57BL6J-638850.11": 10,
        "C57BL6J-638850.12": 11,
        "C57BL6J-638850.13": 12,
        "C57BL6J-638850.14": 13,
        "C57BL6J-638850.15": 14,
        "C57BL6J-638850.16": 15,
        "C57BL6J-638850.17": 16,
        "C57BL6J-638850.18": 17,
        "C57BL6J-638850.19": 18,
        "C57BL6J-638850.24": 19,
        "C57BL6J-638850.25": 20,
        "C57BL6J-638850.26": 21,
        "C57BL6J-638850.27": 22,
        "C57BL6J-638850.28": 23,
        "C57BL6J-638850.29": 24,
        "C57BL6J-638850.30": 25,
        "C57BL6J-638850.31": 27,
        "C57BL6J-638850.32": 28,
        "C57BL6J-638850.33": 29,
        "C57BL6J-638850.35": 31,
        "C57BL6J-638850.36": 32,
        "C57BL6J-638850.37": 33,
        "C57BL6J-638850.38": 34,
        "C57BL6J-638850.39": 35,
        "C57BL6J-638850.40": 36,
        "C57BL6J-638850.42": 38,
        "C57BL6J-638850.43": 39,
        "C57BL6J-638850.44": 40,
        "C57BL6J-638850.45": 41,
        "C57BL6J-638850.46": 42,
        "C57BL6J-638850.47": 44,
        "C57BL6J-638850.48": 45,
        "C57BL6J-638850.49": 46,
        "C57BL6J-638850.50": 47,
        "C57BL6J-638850.51": 48,
        "C57BL6J-638850.52": 49,
        "C57BL6J-638850.54": 51,
        "C57BL6J-638850.55": 52,
        "C57BL6J-638850.56": 54,
        "C57BL6J-638850.57": 55,
        "C57BL6J-638850.58": 56,
        "C57BL6J-638850.59": 57,
        "C57BL6J-638850.60": 59,
        "C57BL6J-638850.61": 60,
        "C57BL6J-638850.62": 61,
        "C57BL6J-638850.64": 65,
        "C57BL6J-638850.66": 69,
        "C57BL6J-638850.67": 71
    }
    if brain_section_label in slice_index_map:
        zindex = slice_index_map[brain_section_label]
    else:
        print(f"\n    [red1]Error: Brain section {brain_section_label} not found\n")
        return

    # Load the annotation boundary image and extract the corresponding slice.
    annotation_boundary_array, boundary_extent = load_region_boundaries(download_base)
    boundary_slice = annotation_boundary_array[zindex, :, :]

    if args.gene is not None:
        # --- GENE MODE: Display gene expression per cell (no binning) ---
        # Load ALL cells metadata (from base)
        all_metadata_file = download_base / 'metadata/MERFISH-C57BL6J-638850/20231215/cell_metadata.csv'
        all_df = load_cell_metadata(all_metadata_file)
        all_df = join_reconstructed_coords(all_df, download_base)
        all_df = join_cluster_details(all_df, download_base)
        all_df = join_cluster_colors(all_df, download_base)
        all_df = join_parcellation_annotation(all_df, download_base)
        all_df = join_parcellation_color(all_df, download_base)
        all_section = filter_brain_section(all_df, args.slice)

        # Load expression data (for the chosen gene) using functions from merfish module.
        adata = m.load_expression_data(download_base, args.gene)
        asubset, gf = m.filter_expression_data(adata, args.gene)
        # Convert the expression data (assumed to be a single gene) into a DataFrame.
        expr_df = asubset.to_df()
        expr_df.columns = [gf.gene_symbol.iloc[0]]  # Rename column to gene symbol

        # Join expression values with the all-cells metadata (using cell label index)
        exp_df = all_section.join(expr_df, how='inner')
        
        # Also prepare the subset (e.g., neurons) for overlay.
        subset_metadata_file = Path('/SSD3/Austen/mdma_saline_social_60um_z_LR_avg_vox_p_tstat1_q0.05_rev_cluster_index_whole_cluster_7_cells_neurons.csv')
        subset_df = load_cell_metadata(subset_metadata_file)
        subset_df = join_reconstructed_coords(subset_df, download_base)
        subset_df = join_cluster_details(subset_df, download_base)
        subset_df = join_cluster_colors(subset_df, download_base)
        subset_df = join_parcellation_annotation(subset_df, download_base)
        subset_df = join_parcellation_color(subset_df, download_base)
        subset_section = filter_brain_section(subset_df, args.slice)
        subset_exp_df = subset_section.join(expr_df, how='inner')

        # Plot: scatter all cells colored by gene expression.
        fig, ax = plt.subplots(figsize=(9, 9))
        sc1 = ax.scatter(exp_df['x_reconstructed'], exp_df['y_reconstructed'],
                         s=1, c=exp_df[gf.gene_symbol.iloc[0]],
                         cmap=plt.cm.magma_r, alpha=0.25, zorder=2)
        cbar = plt.colorbar(sc1, ax=ax)
        cbar.set_label(gf.gene_symbol.iloc[0])
        # Overlay the annotation boundary
        ax.imshow(boundary_slice, cmap=plt.cm.Greys, extent=boundary_extent,
                  alpha=1.0 * (boundary_slice > 0), zorder=3)
        # Overlay subset cells (with larger markers and black edge)
        ax.scatter(subset_exp_df['x_reconstructed'], subset_exp_df['y_reconstructed'],
                   s=8, c=subset_exp_df[gf.gene_symbol.iloc[0]], cmap=plt.cm.magma_r,
                   alpha=1.0, edgecolors='black', zorder=4)
        ax.set_title(f"MERFISH-CCF Slice {args.slice} – {args.gene} Expression")
        ax.set_xlim(0, 11)
        ax.set_ylim(11, 0)
        ax.axis('equal')
        ax.set_xticks([])
        ax.set_yticks([])
        fig.savefig(f"merfish_slice_{args.slice}_{args.gene}.png", dpi=300)
        plt.show()
        
    elif args.color is not None:
        # --- COLOR MODE: Plot cells colored by a metadata field, with a legend ---
        # Load subset metadata (e.g., neurons)
        subset_metadata_file = Path('/SSD3/Austen/mdma_saline_social_60um_z_LR_avg_vox_p_tstat1_q0.05_rev_cluster_index_whole_cluster_7_cells_neurons.csv')
        subset_df = load_cell_metadata(subset_metadata_file)
        subset_df = join_reconstructed_coords(subset_df, download_base)
        subset_df = join_cluster_details(subset_df, download_base)
        subset_df = join_cluster_colors(subset_df, download_base)
        subset_df = join_parcellation_annotation(subset_df, download_base)
        subset_df = join_parcellation_color(subset_df, download_base)
        subset_section = filter_brain_section(subset_df, args.slice)

        # Load all cells metadata from base.
        all_metadata_file = download_base / 'metadata/MERFISH-C57BL6J-638850/20231215/cell_metadata.csv'
        all_df = load_cell_metadata(all_metadata_file)
        all_df = join_reconstructed_coords(all_df, download_base)
        all_df = join_cluster_details(all_df, download_base)
        all_df = join_cluster_colors(all_df, download_base)
        all_df = join_parcellation_annotation(all_df, download_base)
        all_df = join_parcellation_color(all_df, download_base)
        all_section = filter_brain_section(all_df, args.slice)

        # Plot layering: all cells at low opacity and subset with full opacity.
        fig, ax = plt.subplots(figsize=(9, 9))
        ax.scatter(all_section['x_reconstructed'], all_section['y_reconstructed'], 
                   s=0.5, c=all_section[args.color], marker='.', alpha=0.1, zorder=2)
        ax.imshow(boundary_slice, cmap=plt.cm.Greys, extent=boundary_extent, 
                  alpha=1.0 * (boundary_slice > 0), zorder=3)
        sc = ax.scatter(subset_section['x_reconstructed'], subset_section['y_reconstructed'], 
                        s=8, c=subset_section[args.color], marker='.', alpha=1.0, zorder=4)
        # Build legend using the corresponding label (dropping the "_color" suffix if present).
        if args.color.endswith("_color"):
            label_col = args.color.replace("_color", "")
        else:
            label_col = args.color
        unique_labels = np.unique(subset_section[label_col])
        legend_handles = []
        for label in unique_labels:
            matching_colors = subset_section.loc[subset_section[label_col] == label, args.color].unique()
            col = matching_colors[0] if matching_colors.size > 0 else "black"
            legend_handles.append(plt.Line2D([0], [0], marker='o', color=col, linestyle='',
                                              markersize=8, label=str(label)))
        ax.legend(handles=legend_handles, title=label_col, loc='upper right')
        ax.set_title(f"MERFISH-CCF Slice {args.slice}")
        ax.set_xlim(0, 11)
        ax.set_ylim(11, 0)
        ax.axis('equal')
        ax.set_xticks([])
        ax.set_yticks([])
        fig.savefig(f"merfish_slice_{args.slice}_{args.color}.png", dpi=300)
        plt.show()
    else:
        print("\n    [red1]Error: Please specify either a gene (-g) or a color (-c) argument.\n")
    
    verbose_end_msg()


if __name__ == '__main__':
    main()

