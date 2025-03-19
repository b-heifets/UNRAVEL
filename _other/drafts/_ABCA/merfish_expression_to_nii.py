#!/usr/bin/env python3

"""
Use ``merfish_expression_to_nii.py`` from UNRAVEL to make a 3D .nii.gz image of ABCA MERFISH expression data.

Usage:
------
    merfish_expression_to_nii.py -b <abc_download_root> -g <gene> -r <ref_nii> [-n] [-o <output>] [-im] [-v]
"""

import anndata
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
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene(s) to plot.', required=True, nargs='*', action=SM)
    reqs.add_argument('-r', '--ref_nii', help='Path to reference .nii.gz for header info (e.g., image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation.nii.gz)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Output path for the saved .nii.gz image. Default: [imputed_]MERFISH[_neuronal]_expression_maps/<gene>.nii.gz', default=None, action=SM)
    opts.add_argument('-im', '--imputed', help='Use imputed expression data. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Add option for non-neuronal cells

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

    # Print columns
    print(f"\nColumns in cell metadata:")
    print(cell_df_joined.columns)

    if args.neurons:
        # Add: 'neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'
        cell_df_joined = m.join_cluster_details(cell_df, download_base) 

        # Filter out non-neuronal cells
        cell_df_joined = cell_df_joined[cell_df_joined['class'].str.split().str[0].astype(int) <= 29]

    # Load the expression data for all genes (if the gene is in the dataset) 
    adata = m.load_expression_data(download_base, args.gene, imputed=args.imputed)

    for gene in args.gene:
        print(f"\nProcessing gene: {gene}")

        if gene not in adata.var.gene_symbol.values:
            print(f"Gene {gene} not found in the dataset, skipping.")
            continue

        # Define the output path and create the output directory if it doesn't exist
        if args.output:
            output_path = Path(args.output)
        else:
            if args.imputed and args.neurons:
                output_path = Path().cwd() / "imputed_MERFISH_neuronal_expression_maps" / f"{gene}.nii.gz"
            elif args.imputed:
                output_path = Path().cwd() / "imputed_MERFISH_expression_maps" / f"{gene}_imputed.nii.gz"
            elif args.neurons:
                output_path = Path().cwd() / "MERFISH_neuronal_expression_maps" / f"{gene}_neurons.nii.gz"
            else:
                output_path = Path().cwd() / "MERFISH_expression_maps" / f"{gene}.nii.gz"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if the output file already exists
        if output_path.exists():
            print(f"\n    Output file already exists: {output_path}\n")
            continue
        
        # Filter expression data for the specified gene
        asubset, gf = m.filter_expression_data(adata, gene)

        # Print columns
        print(f"\nColumns in cell metadata:")
        print(cell_df_joined.columns)

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