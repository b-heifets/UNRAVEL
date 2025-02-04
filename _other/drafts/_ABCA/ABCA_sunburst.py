#!/usr/bin/env python3

"""
Use ``ABCA_sunburst.py`` from UNRAVEL to generate a sunburst plot of cell type proportions across all ontological levels.

Prereqs: 
    - merfish_filter.py
    
Outputs:
    - path/input_sunburst.csv and [input_path/ABCA_sunburst_colors.csv]

Note:
    - Default sunburst csv location: UNRAVEL/unravel/core/csvs/ABCA_sunburst_IDPath_Abbrv.csv
    - Region info csv: CCFv3-2020_info.csv (or use CCFv3-2017_info.csv or provide a custom CSV with the same columns)

Next steps:
    - Use input_sunburst.csv to make a sunburst plot or regional volumes in Flourish Studio (https://app.flourish.studio/)
    - It can be pasted into the Data tab (categories columns = Depth_`*` columns, Size by = Volumes column)
    - Preview tab: Hierarchy -> Depth to 10, Colors -> paste hex codes from ABCA_sunburst_colors.csv into Custom overrides

Usage:
------ 
    cstats_sunburst -i path/rev_cluster_index.nii.gz [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-rgb] [-scsv sunburst_IDPath_Abbrv.csv] [-icsv CCFv3-2020_info.csv] [-v]
"""

import numpy as np
import pandas as pd
import shutil
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, print_func_name_args_times, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/cell_metadata_filtered.csv', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-lut', '--output_lut', help='Output ABCA_sunburst_colors.csv if flag provided (for ABCA coloring)', action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

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

def sunburst(img, atlas, atlas_res_in_um, output_path, sunburst_csv_path='sunburst_IDPath_Abbrv.csv', info_csv_path='CCFv3-2020_info.csv', output_lut=False):
    """Generate a sunburst plot of regional volumes that cluster comprise across the ABA hierarchy.
    
    Args:
        - img (ndarray)
        - atlas (ndarray)
        - atlas_res_in_um (tuple): the atlas resolution in microns. For example, (25, 25, 25)
        - output_lut (bool): flag to output the RGB values for each abbreviation to a CSV file

    Outputs:
        - CSV file containing the regional volumes for the sunburst plot (input_sunburst.csv)
    """

    volumes_dict = calculate_regional_volumes(img, atlas, atlas_res_in_um)

    if sunburst_csv_path == 'sunburst_IDPath_Abbrv.csv': 
        sunburst_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / sunburst_csv_path)
    else:
        sunburst_df = pd.read_csv(sunburst_csv_path)

    # Load the specified columns from the CSV with CCFv3 info
    if info_csv_path == 'CCFv3-2017_info.csv' or info_csv_path == 'CCFv3-2020_info.csv': 
        ccf_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / info_csv_path, usecols=['lowered_ID', 'abbreviation'])
    else:
        ccf_df = pd.read_csv(info_csv_path, usecols=['lowered_ID', 'abbreviation'])

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

    if output_lut:
        # Save the RGB values for each abbreviation to a CSV file
        rgb_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / 'ABCA' / 'ABCA_sunburst_colors.csv')
        rgb_path = Path(output_path).parent / 'ABCA_sunburst_colors.csv'
        rgb_df.to_csv(rgb_path, index=False)

    return final_df

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the CSV file
    cells_df = pd.read_csv(args.input, usecols=['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster'])

    # Replace blank values in 'neurotransmitter' column with 'NA'
    cells_df['neurotransmitter'] = cells_df['neurotransmitter'].fillna('NA')

    if args.neurons:
        # Filter out non-neuronal cells
        cells_df = cells_df[cells_df['class'].str.split().str[0].astype(int) <= 29]

    # Groupby cluster
    cluster_df = cells_df.groupby('cluster').size().reset_index(name='counts')  # Count the number of cells in each cluster
    cluster_df = cluster_df.sort_values('counts', ascending=False)  # Sort the clusters by the number of cells

    # Add a column for the percentage of cells in each cluster
    cluster_df['percent'] = cluster_df['counts'] / cluster_df['counts'].sum() * 100

    # Drop the 'counts' column
    cluster_df = cluster_df.drop(columns='counts')

    # Join the cells_df with the cluster_df
    cells_df = cells_df.merge(cluster_df, on='cluster')

    # Drop duplicate rows
    cells_df = cells_df.drop_duplicates()

    # Sort by percentage
    cells_df = cells_df.sort_values('percent', ascending=False).reset_index(drop=True)
    print(f'\n{cells_df}\n')

    # Save the output to a CSV file
    output_path = str(Path(args.input)).replace('.csv', '_sunburst.csv')
    cells_df.to_csv(output_path, index=False)

    if args.output_lut:
        lut_path = Path(__file__).parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'ABCA_sunburst_colors.csv'
        shutil.copy(lut_path, Path(args.input).parent / lut_path.name)

    verbose_end_msg()


if __name__ == '__main__':
    main()