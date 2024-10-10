#!/usr/bin/env python3

"""
Use ``/Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf_mpl.py`` from UNRAVEL to plot MERFISH data from the Allen Brain Cell Atlas.

Usage:
------
    /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_ccf_mpl.py -r path/to/root_dir -g gene_name
"""

import anndata
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd
import SimpleITK as sitk
from pathlib import Path
from rich import print
from rich.traceback import install

import merfish as m
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the download base of the Allen brain cell atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene(s) to plot.', required=True, nargs='*', action=SM)
    reqs.add_argument('-r', '--ref_nii', help='Path to reference .nii.gz for header info (e.g., image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation.nii.gz)', required=True, action=SM)


    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Output path for the saved .nii.gz image. Default: None', default=None, action=SM)

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

    download_base = Path(args.base)

    # Load the cell metadata (for the cell_label and brain_section_label [e.g. C57BL6J-638850.0])
    cell_df = m.load_cell_metadata(download_base)

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = m.join_reconstructed_coords(cell_df, download_base)

    # Load the expression data for the specified gene
    adata = m.load_expression_data(download_base)

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