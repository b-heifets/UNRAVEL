#!/usr/bin/env python3

"""
Use ``ABCA_sunburst_expression.py`` from UNRAVEL to calculate mean expression for all cell types in the ABCA and make a sunburst plot.

Prereqs: 
    - merfish_filter.py
    - merfish_join_expression_data.py (use output from this script as input)

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

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import shutil
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


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
    cols = ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster', args.gene]
    cells_df = pd.read_csv(args.input, usecols=cols)

    # Replace blank values in 'neurotransmitter' column with 'NA'
    cells_df['neurotransmitter'] = cells_df['neurotransmitter'].fillna('NA')

    if args.neurons:
        cells_df = cells_df[cells_df['class'].str.split().str[0].astype(int) <= 29]

    # Groupby cluster to calculate the percentage of cells in each cluster
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

    # Calculate mean expression and percent expressing at each hierarchy level
    summary_df = cells_df.copy()
    hierarchy_levels = ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster']
    for level in hierarchy_levels:
        summary_df[f'{level}_mean'] = summary_df[level].map(cells_df.groupby(level)[args.gene].mean())
        summary_df[f'{level}_percent'] = summary_df[level].map(cells_df.groupby(level)[args.gene].apply(lambda x: (x > 0).mean() * 100))

    summary_df = summary_df.drop(columns=[args.gene]).drop_duplicates()
    
    # Save the results
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / str(Path(args.input).name).replace('.csv', '_sunburst_expression_summary.csv')
    summary_df.to_csv(output_path, index=False)
    
    print(f"\nSaved sunburst expression summary to {output_path}")

    # Stack labels and values for LUT files
    label_stack = pd.DataFrame()
    for level in hierarchy_levels:
        label_stack = pd.concat([label_stack, summary_df[level].rename('label')], axis=0)

    # Stack mean expression values and construct the mean expression LUT
    mean_stack = pd.DataFrame()
    for level in hierarchy_levels:
        mean_stack = pd.concat([mean_stack, summary_df[f'{level}_mean'].rename('value')], axis=0)
    mean_df = pd.concat([label_stack, mean_stack], axis=1) # Combine the label stack and the mean stack
    mean_df = mean_df.drop_duplicates()
    mean_df.columns = ['label', 'value']

    # Replace the mean value with the hex color (magma_r)
    mean_df['color'] = mean_df['value'].apply(lambda x: mcolors.rgb2hex(plt.cm.magma_r((x - 0) / (8 - 0))))
    mean_df = mean_df.drop(columns=['value'])

    # Save the mean expression LUT
    mean_path = str(output_path).replace('expression_summary.csv', 'mean_expression_lut.txt')
    for row in mean_df.itertuples(index=False):
        with open(mean_path, 'a') as f:
            f.write(f"{row.label}: {row.color}\n")

    # Stack percent expression values
    percent_stack = pd.DataFrame()
    for level in hierarchy_levels:
        percent_stack = pd.concat([percent_stack, summary_df[f'{level}_percent'].rename('value')], axis=0)
    percent_df = pd.concat([label_stack, percent_stack], axis=1)
    percent_df = percent_df.drop_duplicates()
    percent_df.columns = ['label', 'value']

    # Replace the percent value with the hex color (viridis_r)
    percent_df['color'] = percent_df['value'].apply(lambda x: mcolors.rgb2hex(plt.cm.viridis_r((x - 0) / (100 - 0))))
    percent_df = percent_df.drop(columns=['value'])

    # Save the percent expression LUT
    percent_path = str(output_path).replace('expression_summary.csv', 'percent_expression_lut.txt')
    for row in percent_df.itertuples(index=False):
        with open(percent_path, 'a') as f:
            f.write(f"{row.label}: {row.color}\n")

    verbose_end_msg()


if __name__ == '__main__':
    main()