#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a sunburst plot of regional volumes that cluster comprise across the ABA hierarchy', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/rev_cluster_index.nii.gz (e.g., with valid clusters)', required=True, action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: path/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-rgb', '--output_rgb_lut', help='Output sunburst_RGBs.csv if flag provided (for Allen brain atlas coloring)', action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true')
    parser.epilog = """Usage:    sunburst.py -i path/rev_cluster_index.nii.gz -a path/atlas.nii.gz -v

Prereqs: 
    - validate_clusters.py generates a rev_cluster_index.nii.gz (clusters of significant voxels) and validates them. 
    - Optional: valid_cluster_index.py generates a rev_cluster_index.nii.gz w/ valid clusters.
    
Outputs: path/input_sunburst.csv and [input_path/sunburst_RGBs.csv]
Plot region volumes (https://app.flourish.studio/)
Data tab: Paste in data from csv, categories columns = Depth_* columns, Size by = Volumes column
Preview tab: Hierarchy -> Depth to 10, Colors -> paste RGB codes into Custom overrides"""
    return parser.parse_args()


def calculate_regional_volumes(img, atlas, atlas_res_in_um):
    """Calculate the volumes of labeled regions in the input image.

    Args:
        - img (ndarray): the input image ndarray.
        - atlas (ndarray): the atlas ndarray.
        - atlas_res_in_um (tuple): the atlas resolution in in microns.
    
    Returns:
        - volumes_dict (dict): a dictionary of region volumes (key = region ID, value = volume in mm^3)
    """
    
    img[img > 0] = 1 # Binarize input image
    img = img.astype(np.int16)
    img *= atlas
    uniq_values, counts = np.unique(img, return_counts=True)
    volumes = (atlas_res_in_um**3 * counts) / 1000000000  # Convert voxel counts to cubic mm
    uniq_values = uniq_values[1:]
    volumes = volumes[1:]

    return dict(zip(uniq_values, volumes))

def sunburst(img, atlas, atlas_res_in_um, output_path, output_rgb_lut=False):
    """Generate a sunburst plot of regional volumes that cluster comprise across the ABA hierarchy.
    
    Args:
        - img (ndarray)
        - atlas (ndarray)
        - atlas_res_in_um (tuple): the atlas resolution in microns. For example, (25, 25, 25)
        - output_rgb_lut (bool): flag to output the RGB values for each abbreviation to a CSV file

    Outputs:
        - CSV file containing the regional volumes for the sunburst plot (input_sunburst.csv)
    """

    volumes_dict = calculate_regional_volumes(img, atlas, atlas_res_in_um)

    sunburst_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / 'sunburst_IDPath_Abbrv.csv')
    ccf_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / 'CCFv3_info.csv', usecols=['lowered_ID', 'abbreviation'])

    # Create a mapping from region ID to volume
    histo_df = pd.DataFrame(list(volumes_dict.items()), columns=['Region', 'Volume_(mm^3)'])
    merged_df = pd.merge(histo_df, ccf_df, left_on='Region', right_on='lowered_ID', how='inner') 

    # Determine the maximum depth for each abbreviation
    depth_columns = [f'Depth_{i}' for i in range(10)]
    sunburst_df['max_depth_abbr'] = sunburst_df[depth_columns].apply(lambda row: row.dropna().iloc[-1], axis=1)

    # Merge the volumes into sunburst_df based on the finest granularity abbreviation
    final_df = sunburst_df.merge(merged_df, left_on='max_depth_abbr', right_on='abbreviation', how='left')

    # Drop rows without volume data
    final_df = final_df[final_df['Volume_(mm^3)'].notna()]

    # Drop columns not needed for the sunburst plot
    final_df.drop(columns=['max_depth_abbr', 'Region', 'lowered_ID', 'abbreviation'], inplace=True)

    # Save the output to a CSV file
    final_df.to_csv(output_path, index=False)


    if output_rgb_lut:
        # Save the RGB values for each abbreviation to a CSV file
        rgb_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / 'sunburst_RGBs.csv')
        rgb_path = Path(output_path).parent / 'sunburst_RGBs.csv'
        rgb_df.to_csv(rgb_path, index=False)

    return final_df

def main():
    args = parse_args()

    # Load the input image and convert to numpy array
    nii = nib.load(args.input)
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

    # Load the atlas image and convert to numpy array
    atlas_nii = nib.load(args.atlas)
    atlas = np.asanyarray(atlas_nii.dataobj, dtype=atlas_nii.header.get_data_dtype()).squeeze()

    # Get the atlas resolution
    atlas_res = atlas_nii.header.get_zooms() # (x, y, z) in mm
    xyx_res_in_mm = atlas_res[0]
    xyz_res_in_um = xyx_res_in_mm * 1000

    output_name = str(Path(args.input).name).replace('.nii.gz', '_sunburst.csv')
    output_path = Path(args.input).parent / output_name
    
    sunburst_df = sunburst(img, atlas, xyz_res_in_um, output_path, args.output_rgb_lut)

    print(f'\n\n[magenta bold]{output_name}[/]:')    
    print(f'\n{sunburst_df}\n')


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()