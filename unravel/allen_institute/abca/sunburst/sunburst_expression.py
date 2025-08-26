#!/usr/bin/env python3

"""
Use ``abca_sunburst_expression`` or ``sbe`` from UNRAVEL to calculate mean expression for all cell types in the ABCA and make a sunburst plot.

Prereqs: 
    - ``abca_merfish_filter`` and ``merfish_join_expression_data.py``
    - Or: ``RNAseq_expression.py`` and ``RNAseq_filter.py``

Outputs:
    - path/input_sunburst_expression_thr<value>.csv, input_mean_expression_lut.txt, and input_percent_expression_thr<value>_lut.txt

Note:
    - LUT location: unravel/core/csvs/ABCA/WMB_sunburst_colors.csv

Next steps:
    - Use input_sunburst.csv to make a sunburst plot or regional volumes in Flourish Studio (https://app.flourish.studio/)
    - It can be pasted into the Data tab (categories columns = cell type columns, Size by = percent column)
    - Preview tab: Hierarchy -> Depth to 5, Colors -> paste content of ..._colors.csv into Custom overrides

Usage:
------ 
    abca_sunburst_expression -i path/VTA_DA_cells_Th_expression.csv -g gene [-o path/out_dir] [-n] [-v]
"""

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import shutil
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.allen_institute.abca.sunburst.sunburst import filter_non_neuronal_cells
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

# TODO: Update docstring with commands for other scripts in prereqs. Mean for all cells not saved yet.

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/cells_filtered_exp.csv', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-s', '--species', help='Species to analyze ("mouse" or "human"). Default: mouse', default='mouse', action=SM)
    opts.add_argument('-n', '--neurons', help='Filter out non-neuronal cells. Default: False', action='store_true', default=False)
    opts.add_argument('-c', '--color_max', help='Maximum value for the color scale. Default: 10', default=10, type=float, action=SM)
    opts.add_argument('-t', '--threshold', help='Log2(CPM+1) threshold for percent gene expression. Default: 6', default=6, type=float, action=SM)
    opts.add_argument('-o', '--output', help='Output dir path. Default: ABCA_sunburst_cmax10_thr6/', default=None, action=SM)
    opts.add_argument('-a', '--all', help='Save mean expression and percent expressing for all cells. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    species = args.species.lower()
    if species not in ['mouse', 'human']:
        raise ValueError(f"Species '{species}' not recognized. Please use 'mouse' or 'human'.")
    print(f"\nUsing species: {species}\n")

    # Load the CSV file
    if species == 'mouse':
        cols = ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster', args.gene]
    elif species == 'human':
        cols = ['neurotransmitter', 'supercluster', 'cluster', 'subcluster', args.gene]
    expected = set(cols)
    missing = expected - set(pd.read_csv(args.input, nrows=1).columns)
    if missing:
        raise ValueError(f"Missing expected columns for {species} data: {missing}")
    cells_df = pd.read_csv(args.input, usecols=cols)

    # Replace blank values in 'neurotransmitter' column with 'NA'
    cells_df['neurotransmitter'] = cells_df['neurotransmitter'].fillna('NA')

    if args.neurons:
        cells_df = filter_non_neuronal_cells(cells_df, species)

    # Groupby the finest cell types to calculate the percentage of cells
    fine_level_col = 'subcluster' if 'subcluster' in cells_df.columns else 'cluster'
    fine_df = cells_df.groupby(fine_level_col).size().reset_index(name='counts')  # Count the number of cells for each cell type
    fine_df = fine_df.sort_values('counts', ascending=False)  # Sort the cell types by the number of cells

    # Add a column for the percentage of cells
    fine_df['percent'] = fine_df['counts'] / fine_df['counts'].sum() * 100

    # Drop the 'counts' column
    fine_df = fine_df.drop(columns='counts')

    # Join the cells_df with the fine_df
    cells_df = cells_df.merge(fine_df, on=fine_level_col)

    # Drop duplicate rows
    cells_df = cells_df.drop_duplicates()

    # Sort by percentage
    cells_df = cells_df.sort_values('percent', ascending=False).reset_index(drop=True)

    # Calculate the mean expression and percent expressing for all cells in cells_df
    all_mean = cells_df[args.gene].mean()
    all_percent = (cells_df[args.gene] > args.threshold).mean() * 100

    # Create the output directory
    if args.output is None:
        output_dir = Path(args.input).parent / f'ABCA_sunburst_cmax{args.color_max}_thr{args.threshold}'
    else:
        output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the mean expression and percent expressing for all cells (.txt)
    if args.all:
        output_path = output_dir / str(Path(args.input).name).replace('.csv', f'_sunburst_expression_thr{args.threshold}_all.txt')
        with open(output_path, 'w') as f:
            f.write(f"all_mean: {all_mean}\nall_percent (threshold: {args.threshold}): {all_percent}")
        print(f"\nSaved mean expression and percent expressing for all cells to {output_path}")

    # Calculate mean expression and percent expressing at each hierarchy level
    summary_df = cells_df.copy()
    if species == 'mouse':
        hierarchy_levels = ['neurotransmitter', 'class', 'subclass', 'supertype', 'cluster']
    elif species == 'human':
        hierarchy_levels = ['neurotransmitter', 'supercluster', 'cluster', 'subcluster']
    for level in hierarchy_levels:
        summary_df[f'{level}_mean'] = summary_df[level].map(cells_df.groupby(level)[args.gene].mean())
        summary_df[f'{level}_percent'] = summary_df[level].map(cells_df.groupby(level)[args.gene].apply(lambda x: (x > args.threshold).mean() * 100))

    summary_df = summary_df.drop(columns=[args.gene]).drop_duplicates()
    
    # Save the results
    output_path = output_dir / str(Path(args.input).name).replace('.csv', f'_sunburst_expression_thr{args.threshold}.csv')
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
    mean_df['color'] = mean_df['value'].apply(lambda x: mcolors.rgb2hex(plt.cm.magma_r((x - 0) / (args.color_max - 0))))
    mean_df = mean_df.drop(columns=['value'])

    # Save the mean expression LUT
    mean_path = str(output_path).replace(f'_expression_thr{args.threshold}.csv', '_mean_expression_lut.txt')
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
    percent_path = str(output_path).replace(f'_expression_thr{args.threshold}.csv', f'_percent_expression_thr{args.threshold}_lut.txt')
    for row in percent_df.itertuples(index=False):
        with open(percent_path, 'a') as f:
            f.write(f"{row.label}: {row.color}\n")
    
    if species == 'mouse':
        lut_path = Path(__file__).parent.parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'WMB_sunburst_colors.csv'
    elif species == 'human':
        lut_path = Path(__file__).parent.parent.parent.parent.parent / 'unravel' / 'core' / 'csvs' / 'ABCA' / 'WHB_sunburst_colors.csv'
    shutil.copy(lut_path, output_path.parent / lut_path.name)
    
    verbose_end_msg()


if __name__ == '__main__':
    main()