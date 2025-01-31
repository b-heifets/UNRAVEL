#!/usr/bin/env python3

"""
Use ``merfish_cluster.py`` from UNRAVEL to filter MERFISH cell metadata by cluster.

Prereqs:
    - Use CCF30_to_MERFISH.py to warp the cluster image to MERFISH-CCF space

Notes:
    - This script assumes that there is only one cluster
    - 1) Binarize the cluster map
    - 2) Determine the bounding box of the cluster
    - 3) Filter the cell metadata using the bounding box info
    - 4a) Loop through each cell and filter out cells whose reconstructed coordinates fall are external to the cluster
    - 4b) Or, convert the filtered cell metadata to a 3D image using cell IDs as the intensity values 
    - 5b) Multiply the 3D image by the cluster image to zero out cellular voxels that are not in the cluster
    - 6b) Convert non-zero voxels in the 3D cell image into a DataFrame (cell ID, x, y, z)
    - 7b) Use the cells in cluster DataFrame to check that cells do not overlap and to filter cell metadata by cell ID
    - Finally, save the filtered cell metadata to a new CSV file

Next steps:
    - Use the filtered cell metadata to examine cell type prevalence or gene expression
    - For looking at gene expression, load the filtered cell metadata and join it with the expression data for the gene(s) of interest

Usage:
------
    /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf_mpl.py -b path/to/root_dir -i cluster.nii.gz
"""

import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

# 208 685 651 75 31 7 0 1  # <xmin> <xsize> <ymin> <ysize> <zmin> <zsize> <tmin> <tsize>

import merfish as m
from unravel.cluster_stats.validation import cluster_bbox
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.core.img_io import load_nii


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/cluster.nii.gz', required=True, action=SM)
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Output path for cell metadata after filtering by cluster. Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def add_merfish_slice_to_3d_img(z, cell_df_joined, asubset, gf, gene, img):
    brain_section = cell_df_joined[cell_df_joined['z_reconstructed'] == z]['brain_section_label'].values[0]
    slice_index_map = m.slice_index_dict()

    if brain_section not in slice_index_map:
        return img

    print(f"    Processing brain section: {brain_section}")
    # pred = (cell_df_joined['z_reconstructed'] == z)
    # section = cell_df_joined[pred]
    section = cell_df_joined[cell_df_joined['z_reconstructed'] == z]
    exp_df = m.create_expression_dataframe(asubset, gf, section)
    points_ndarray = exp_df[['x_reconstructed', 'y_reconstructed', gene]].values
    img_slice = m.points_to_img_sum(points_ndarray, x_size=1100, y_size=1100, pixel_size=10)
    zindex = m.section_to_zindex(brain_section)
    img[:, :, zindex] = img_slice
    return img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the cluster image
    cluster_img = load_nii(args.input)

    # Binarize
    cluster_img[cluster_img > 0] = 1

    # Get the bounding box of the cluster
    _, xmin, xmax, ymin, ymax, zmin, zmax = cluster_bbox(1, cluster_img)

    # Load the cell metadata
    download_base = Path(args.base)

    # Load the cell metadata
    cell_df = m.load_cell_metadata(download_base)

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = m.join_reconstructed_coords(cell_df, download_base)

    # Add the classification levels and the corresponding color.
    cell_df_joined = m.join_cluster_details(cell_df_joined, download_base)

    # Add the cluster colors
    cell_df_joined = m.join_cluster_colors(cell_df_joined, download_base)
    
    # Add the parcellation annotation
    cell_df_joined = m.join_parcellation_annotation(cell_df_joined, download_base)

    # Add the parcellation color
    cell_df_joined = m.join_parcellation_color(cell_df_joined, download_base)

    print(f'\n{cell_df_joined=}\n')
    print(f'\n{xmin=}\n')
    print(f'\n{xmax=}\n')
    print(f'\n{ymin=}\n')
    print(f'\n{ymax=}\n')
    print(f'\n{zmin=}\n')
    print(f'\n{zmax=}\n')

    # Filter the cell metadata by the bounding box of the cluster using the reconstructed coordinates (x_reconstructed, y_reconstructed, z_reconstructed)
    cell_df_bbox_filter = cell_df_joined[cell_df_joined['x_reconstructed'] >= xmin &
                                        cell_df_joined['x_reconstructed'] <= xmax &
                                        cell_df_joined['y_reconstructed'] >= ymin &
                                        cell_df_joined['y_reconstructed'] <= ymax &
                                        cell_df_joined['z_reconstructed'] >= zmin & 
                                        cell_df_joined['z_reconstructed'] <= zmax]
    
    print(f'\n{cell_df_bbox_filter=}\n')
    


    import sys ; sys.exit()

    # Loop through each cell and filter out cells whose reconstructed coordinates fall are external to the cluster




    download_base = Path(args.base)

    # Load the cell metadata (for the cell_label and brain_section_label [e.g. C57BL6J-638850.0])
    cell_df = m.load_cell_metadata(download_base)

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = m.join_reconstructed_coords(cell_df, download_base)

    # Load the expression data for all genes (if the gene is in the dataset) 
    adata = m.load_expression_data(download_base, args.gene)

    for gene in args.gene:
        print(f"\nProcessing gene: {gene}")

        if gene not in adata.var.gene_symbol.values:
            print(f"Gene {gene} not found in the dataset, skipping.")
            continue

        if args.output:
            output_path = Path(args.output)
        else:
            output_path = download_base / f"{gene}_MERFISH-CCF.nii.gz"

        # Check if the output file already exists
        if output_path.exists():
            print(f"\n    Output file already exists: {output_path}\n")
            continue
        
        # Filter expression data for the specified gene
        asubset, gf = m.filter_expression_data(adata, gene)

        # Get the unique z_positions and their corresponding MERFISH slice indices
        z_positions = np.sort(cell_df_joined['z_reconstructed'].unique())

        # Create an empty 3D image with shape
        img = np.zeros((1100, 1100, 76))

        # Loop through all z positions and add the expression data to the image at the corresponding z index
        for z in z_positions:
            img = add_merfish_slice_to_3d_img(z, cell_df_joined, asubset, gf, gene, img)

        # Save the image as a .nii.gz file
        ref_nii = nib.load(args.ref_nii)
        nii_img = nib.Nifti1Image(img, affine=ref_nii.affine, header=ref_nii.header)
        nib.save(nii_img, str(output_path))
        print(f"\n    Saved image to {output_path}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()