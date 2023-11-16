#! /usr/bin/env python3

from pathlib import Path
import os
import argparse
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Calculate regional volumes from cluster index and outputs csvs')
    parser.add_argument('-i', '--index', help='path/rev_cluster_index.nii.gz (e.g., from fdr.sh)', default=None, metavar='') 
    parser.add_argument('-a', '--atlas', help='path/img.nii.gz. Default: gubra_ano_split_25um.nii.gz', default="/usr/local/unravel/atlases/gubra/gubra_ano_split_25um.nii.gz", metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Outputs: .csv files in path/*_cluster_index.nii.gz/regional_volumes/
    - *region_volumes_split.csv: volumes for each hemisphere
    - *region_volumes_combined.csv: combined volumes for left and right hemispheres
    - *sunburst.csv: volumes for each region in ABA hierarchy (for sunburst plot in Fluorish)
    - sunburst_RGBs.csv: RGB values for each region in ABA hierarchy (for sunburst plot)
    """
    return parser.parse_args()

print_func_name_args_times()
def region_volumes(cluster_index_path, atlas_path):
    """Generate 16 bit intensity histogram CSV for regional volumes from cluster index and atlas"""

    # Load cluster index and atlas
    cluster_index = load_3D_img(cluster_index_path, desired_axis_order='xyz', return_res=False)
    atlas, xy_res, z_res = load_3D_img(atlas_path, desired_axis_order='xyz', return_res=True)

    # Zero out voxels in atlas where cluster index is 0. Otherwise retain original intensity
    ABA_index = np.where(cluster_index == 0, 0, atlas)

    # Generate histogram CSV
    histo, _ = np.histogram(ABA_index, bins=65536, range=(0, 65535))

    # Calculate volumes in cubic mm
    volumes_in_cubic_mm = ((xy_res**2) * z_res) * histo / 1000000000

    # Load csv and get region IDs
    region_volumes_df = pd.read_csv(Path(__file__).parent / 'gubra__regionID_side_IDpath_region_abbr.csv')
    region_ids = region_volumes_df['Region_ID']

    # Slice np.array using list to get regional volumes
    region_volumes = volumes_in_cubic_mm[region_ids]

    # Add header/column to dataframe
    region_volumes_df['Volume_(mm^3)'] = region_volumes 

    # Preserve side-specific volumes
    region_volumes_split_df = region_volumes_df.copy()

    # Sum volumes for left and right sides and reduce dataframe to 596 rows
    group_cols = ['Region_ID', 'Side', 'ID_Path', 'Region', 'Abbr']
    region_volumes_combined_df = region_volumes_df.groupby(group_cols, as_index=False)['Volume_(mm^3)'].sum()

    # Change values in Side column to 'LR'
    region_volumes_combined_df['Side'] = 'LR'

    # Load dataframe template (depths in ABA hierarchy w/ region abbreviations)
    sunburst_df = pd.read_csv(Path(__file__).parent / 'sunburst_IDPath_Abbrv.csv')
    
    # Add combined volumes to sunburst_df
    sunburst_df['Volume_(mm^3)'] = region_volumes_combined_df['Volume_(mm^3)']

    # Exclude missing regions
    region_volumes_split_df = region_volumes_split_df[region_volumes_split_df['Volume_(mm^3)'] > 0]
    region_volumes_combined_df = region_volumes_combined_df[region_volumes_combined_df['Volume_(mm^3)'] > 0]
    sunburst_df = sunburst_df[sunburst_df['Volume_(mm^3)'] > 0]

    # Define output paths
    output_dir = Path(Path(args.index).parent, 'regional_volumes')
    os.makedirs(output_dir, exist_ok=True)
    region_volumes_split_output = Path(output_dir, Path(args.index).name.replace('.nii.gz', '_region_volumes_split.csv'))
    region_volumes_combined_output = Path(output_dir, Path(args.index).name.replace('.nii.gz', '_region_volumes_combined.csv'))
    sunburst_output = Path(output_dir, Path(args.index).name.replace('.nii.gz', '_sunburst.csv'))

    # Save outputs
    region_volumes_split_df.to_csv(region_volumes_split_output, index=False)
    region_volumes_combined_df.to_csv(region_volumes_combined_output, index=False)
    sunburst_df.to_csv(sunburst_output, index=False)

    # Copy sunburst_RGBs.csv to output dir
    sunburst_RGBs = Path(__file__).parent / 'sunburst_RGBs.csv'
    os.system(f"cp {sunburst_RGBs} {output_dir}")

    print(f"\n{region_volumes_combined_df}")


def main():
    region_volumes(args.index, args.atlas)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
