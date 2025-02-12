#!/usr/bin/env python3

"""
Use ``ABCA_sunburst_expression.py`` from UNRAVEL to filter ABCA sunburst expression data, keeping cells with high expression at any level (class, subclass, supertype, cluster).

Prereqs:
    - ABCA_suburst_expression.py

Notes:
    - Use LUTs from ABCA_suburst_expression.py for coloring the sunburst plot.

Usage for first run:
--------------------
./ABCA_sunburst_filtered.py -i path/main_ABCA_sunburst_expression.csv -g geneX -o ABCA_sunburst_filtered/ [-n] [-c 10] [-t 6] 

Usage to apply filtering from another dataset:
----------------------------------------------
./ABCA_sunburst_filtered.py -i path/_main_ABCA_sunburst_filter.csv -a path/secondary_ABCA_sunburst_expression.csv -g geneX -o new_output [-n] [-c 10] [-t 6]
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
    reqs.add_argument('-i', '--input', help='path/main_ABCA_sunburst_expression.csv (the primary file for determining filtering by expression)', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-t', '--threshold', help='Log2(CPM+1) threshold for percent gene expression (rec: use same thresh as for ABCA_sunburst_expression.py). Default: 6', default=6, type=float, action=SM)
    opts.add_argument('-l', '--level', help='Level to filter on. Default: supertype', default='supertype', action=SM)
    opts.add_argument('-o', '--output', help='Output dir path. Default: ABCA_sunburst_filtered_thr6_<level>', default=None, action=SM)
    opts.add_argument('-a', '--apply_to', help='path/secondary_ABCA_sunburst_expression.csv (the secondary file to filter based on the primary file)', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    main_sunburst_exp_df = pd.read_csv(args.input)
    print('\nMain sunburst expression data:')
    print(main_sunburst_exp_df)

    # Keep cells that have high mean expression (e.g., >= 6) of the gene of interest in 
    cell_mean_col = f'{args.level}_mean'
    cells_df_filtered = main_sunburst_exp_df[
        (main_sunburst_exp_df[cell_mean_col] >= args.threshold)
    ]

    print('\nMain sunburst expression data after filtering:')
    print(cells_df_filtered)

    # Save the filtered results
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(f'ABCA_sunburst_filtered_thr{args.threshold}_{args.level}')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / str(Path(args.input).name).replace('.csv', f'_filtered.csv')
    cells_df_filtered.to_csv(output_path, index=False)

    # Copy the mean expression LUT
    mean_lut = str(args.input).replace(f'expression_thr{args.threshold}.csv', 'mean_expression_lut.txt')
    if Path(mean_lut).exists():
        shutil.copy(mean_lut, output_dir)

    if args.apply_to:
        # Get list of clusters with high expression
        filtered_clusters = cells_df_filtered['cluster'].unique()
        print(f"\nClusters with high expression: {filtered_clusters}")

        # Load the secondary dataset
        secondary_sunburst_exp_df = pd.read_csv(args.apply_to)
        print('\nSecondary sunburst expression data:')
        print(secondary_sunburst_exp_df)

        # Filter the secondary dataset
        secondary_cells_df_filtered = secondary_sunburst_exp_df[secondary_sunburst_exp_df['cluster'].isin(filtered_clusters)]
        print('\nSecondary sunburst expression data after filtering:')
        print(secondary_cells_df_filtered)

        # Save the filtered results
        output_path = output_dir / str(Path(args.apply_to).name).replace('.csv', f'_filtered_with_{Path(args.input).name}')
        secondary_cells_df_filtered.to_csv(output_path, index=False)

        # Copy the mean expression LUT
        if str(args.apply_to).endswith(f'expression_thr{args.threshold}.csv'):  # scRNA-seq data
            mean_lut = str(args.apply_to).replace(f'expression_thr{args.threshold}.csv', 'mean_expression_lut.txt')
        elif str(args.apply_to).endswith(f'expression_summary.csv'):  # MERFISH data
            mean_lut = str(args.apply_to).replace(f'expression_summary.csv', 'mean_expression_lut.txt')
        if Path(mean_lut).exists():
            shutil.copy(mean_lut, output_dir)
    
    verbose_end_msg()


if __name__ == '__main__':
    main()
