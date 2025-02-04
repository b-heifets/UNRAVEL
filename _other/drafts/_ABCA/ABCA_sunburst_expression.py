#!/usr/bin/env python3

"""
Use ``ABCA_sunburst_expression.py`` from UNRAVEL to calculate mean expression for all cell types in the ABCA and make a sunburst plot.

Prereqs: 
    - merfish_filter.py
    - merfish_join_expression_data.py (use output from this script as input)
    
Outputs:
    - input_sunburst.csv
    - input_sunburst_mean_exp.csv (for mean expression)
    - input_sunburst_mean_exp_colors.csv
    - input_sunburst_percent_exp.csv (for percent expression)
    - input_sunburst_percent_exp_colors.csv
    - input_overall_metrics.txt (mean expression, percent expression)

Note:
    - LUT location: unravel/core/csvs/ABCA/ABCA_sunburst_colors.csv

Next steps:
    - Use input_sunburst.csv to make a sunburst plot or regional volumes in Flourish Studio (https://app.flourish.studio/)
    - It can be pasted into the Data tab (categories columns = cell type columns, Size by = percent column)
    - Preview tab: Hierarchy -> Depth to 5, Colors -> paste content of ..._colors.csv into Custom overrides

Usage:
------ 
    ABCA_sunburst_expression.py -i path/VTA_DA_cells_Th_expression.csv -g gene [-o path/out_dir] [-n] [-v]
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
    reqs.add_argument('-i', '--input', help='path/cells_filtered_exp.csv', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Output dir path. Default: ABCA_sunburst_expression', default='ABCA_sunburst_expression', action=SM)

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

    # Save the cell type sunburst to a CSV file
    output_dir = Path(args.output)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    sunburst_path = output_dir / str(Path(args.input).name).replace('.csv', '_sunburst.csv')
    cells_df.to_csv(sunburst_path, index=False)

    # Save the cell type LUT
    lut_path = Path(__file__).parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'ABCA_sunburst_colors.csv'
    shutil.copy(lut_path, Path(args.output) / lut_path.name)

    # Calculate the mean expression for each 
    cells_exp_df = pd.read_csv(args.input, usecols=['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster', args.gene])

    # Replace blank values in 'neurotransmitter' column with 'NA'
    cells_exp_df['neurotransmitter'] = cells_exp_df['neurotransmitter'].fillna('NA')

    if args.neurons:
        # Filter out non-neuronal cells
        cells_exp_df = cells_exp_df[cells_exp_df['class'].str.split().str[0].astype(int) <= 29]

    # Calculate the mean expression for each cluster
    
    mean_exp_df = cells_exp_df.groupby('cluster')[args.gene].mean().reset_index()

    # Join cells_df with mean_exp_df using 'cluster'
    cells_df = cells_df.merge(mean_exp_df, on='cluster')

    # Calculate the percentage of cells expressing the gene in each cluster
    cells_exp_df['precent_expressing'] = cells_exp_df[args.gene] > 0

    percent_exp_df = cells_exp_df.groupby('cluster')['precent_expressing'].mean().reset_index()
    percent_exp_df['precent_expressing'] = percent_exp_df['precent_expressing'] * 100

    # Join cells_df with percent_exp_df using 'cluster'
    cells_df = cells_df.merge(percent_exp_df, on='cluster')
    print(f'\n{cells_df}\n')

    # Save the mean expression to a CSV file
    output_path = output_dir / str(Path(args.input).name).replace('.csv', '_sunburst_expression.csv')
    cells_df.to_csv(output_path, index=False)

    verbose_end_msg()


if __name__ == '__main__':
    main()