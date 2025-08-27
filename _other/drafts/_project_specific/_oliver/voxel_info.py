#!/usr/bin/env python3

"""
Use ``voxel_info.py`` from UNRAVEL to compute voxel statistics for a set of images.

Creates df with columns:
    - x, y, z, (voxel coordinates)
    - <group>_??, (column name: group name, sample number; values: intensities)
    - <group1>_mean, <group2>_mean, 
    - <group1>_var, var_<group2>_var, 
    - mask,
    - vox_p_tstat1, vox_p_tstat2,
    - rev_cluster_index_1, rev_cluster_index_2, ... (cluster IDs for each voxel)
    - region_id,
    - region (OLF, HPF, RHP, CTXsp, STR, PAL, TH, HY, MB, and one subdivision below ISO (VIS, AUD, ORB etc.))

Usage:
------
    voxel_info -i '<asterisk>.nii.gz' 
"""

import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.img_io import load_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Glob pattern for input .nii.gz files (e.g., '*.nii.gz'). Default: '*.nii.gz'", default='*.nii.gz', nargs='*', action=SM)
    opts.add_argument('-mi', '--more_inputs', help='Paths to additional images to append to the DataFrame. Default: None', default=None, nargs='*', action=SM)
    opts.add_argument('-mic', '--mi_cols', help='Column names for the additional images (same order as -mi; rec: use region_id for the atlas. Default: None', default=None, nargs='*', action=SM)
    opts.add_argument('-o', '--output', help='Output parquet file path. Default: voxel_info.parquet', default='voxel_info.parquet', action=SM)
    opts.add_argument('-c', '--csv', help='Path to csv with region info (e.g., CCFv3-2020_info.csv). Default: None', default=None, action=SM)
    opts.add_argument('-ri', '--region_id', help='Region ID column. Default: structure_ID', default='structure_ID', action=SM)
    opts.add_argument('-r', '--region', help='Region name column. Default: region', default='region', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def img_to_df(img, col_name):
    """Convert a 3D ndarray to a DataFrame.

    Parameters:
        - img (np.ndarray): the 3D ndarray of the image
        - col_name (str): the name of the column to be created in the DataFrame (will contain the intensities)
    """

    # Get the voxel coordinates
    z_coords, y_coords, x_coords = np.indices(img.shape)

    # Flatten the arrays
    x_coords = x_coords.flatten()
    y_coords = y_coords.flatten()
    z_coords = z_coords.flatten()
    intensity = img.flatten()

    df = pd.DataFrame({
        'x': x_coords,
        'y': y_coords,
        'z': z_coords,
        col_name: intensity
    })

    return df

def append_img_to_df(df, img, col_name):
    """Append intensities from a 3D ndarray to a matching DataFrame.

    Parameters:
        - df (pd.DataFrame): the DataFrame containing voxel coordinate columns: x, y, z
        - img (np.ndarray): the 3D ndarray of the image (same shape as the image used to create the DataFrame)
        - col_name (str): the name of the column to be created in the DataFrame (will contain the intensities)
    """
    intensity = img.flatten()
    df[col_name] = intensity
    return df

def csv_to_img(csv_path, img_shape, col_name):
    """Load the voxel coordinates from a CSV file.

    Parameters:
        - csv_path (str): the path to the CSV file
        - img_shape (tuple): the shape of the 3D ndarray to be created (z, y, x)
        - col_name (str): the name of the column containing the intensities

    Returns:
        - df (pd.DataFrame): the DataFrame containing the voxel coordinates
    """
    df = pd.read_csv(csv_path)
    img = np.zeros(img_shape)
    img[df['z'], df['y'], df['x']] = df[col_name]
    return img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii_paths = match_files(args.input)

    nii_names = [str(nii_path.name).removesuffix(".nii.gz") for nii_path in nii_paths]
    sample_cols = [f"{nii_name.split('_')[0]}_{nii_name.split('_')[1]}".replace("sample", "") for nii_name in nii_names] 

    # Create the initial DataFrame from the first image
    img = load_nii(nii_paths[0])
    df = img_to_df(img, sample_cols[0])

    # Append the intensities from the remaining images
    for nii_path, sample_col in zip(nii_paths[1:], sample_cols[1:]):
        df = append_img_to_df(df, load_nii(nii_path), sample_col)

    # Group level statistics
    groups = sorted(set([nii_name.split('_')[0] for nii_name in nii_names]))
    if len(groups) != 2:
        raise ValueError(f"Expected exactly two groups, found: {groups}")
    group1, group2 = groups

    print(f'\n{group1=}\n')
    print(f'\n{group2=}\n')

    # Columns matching group 
    group1_cols = [col for col in df.columns if group1 in col]
    group2_cols = [col for col in df.columns if group2 in col]

    print(f'\n{group1_cols=}\n')
    print(f'\n{group2_cols=}\n')

    # Add a mean column for each group
    df[f'{group1}_mean'] = df[group1_cols].mean(axis=1)
    df[f'{group2}_mean'] = df[group2_cols].mean(axis=1)

    # Add a variance column for each group
    df[f'{group1}_var'] = df[group1_cols].var(axis=1)
    df[f'{group2}_var'] = df[group2_cols].var(axis=1)

    # Add intensities from additional images
    if args.more_inputs is not None:
        for nii_path, col_name in zip(args.more_inputs, args.mi_cols):
            df = append_img_to_df(df, load_nii(nii_path), col_name)

    # Add region info
    if args.csv is not None:
        region_info_df = pd.read_csv(args.csv, usecols=[args.region_id, args.region])

        # Use the 'region_id' col to add a 'region' col (from the region_info_df)
        if args.region_id not in region_info_df.columns:
            raise KeyError(f"Column '{args.region_id}' not found in region info CSV.")
        df = df.merge(region_info_df, left_on='region_id', right_on=args.region_id, how='left')
    
    print(f'\n{df}\n')

    # Save the DataFrame
    df.to_parquet(args.output, engine="pyarrow", compression="snappy")

    verbose_end_msg()


if __name__ == '__main__':
    main()