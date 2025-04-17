#!/usr/bin/env python3

"""
Use ``abca_sunburst`` or ``sb`` from UNRAVEL to generate a sunburst plot of cell type proportions across all ontological levels.

Prereqs: 
    - merfish_filter.py
    
Outputs:
    - path/input_sunburst.csv and [input_path/ABCA_sunburst_colors.csv]

Note:
    - LUT location: unravel/core/csvs/ABCA/ABCA_sunburst_colors.csv

Next steps:
    - Use input_sunburst.csv to make a sunburst plot or regional volumes in Flourish Studio (https://app.flourish.studio/)
    - It can be pasted into the Data tab (categories columns = cell type columns, Size by = percent column)
    - Preview tab: Hierarchy -> Depth to 5, Colors -> paste hex codes from ABCA_sunburst_colors.csv into Custom overrides

Usage:
------ 
    abca_sunburst -i path/cell_metadata_filtered.csv [-n] [-l] [-v]
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
    opts.add_argument('-l', '--output_lut', help='Output ABCA_sunburst_colors.csv if flag provided (for ABCA coloring)', action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

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