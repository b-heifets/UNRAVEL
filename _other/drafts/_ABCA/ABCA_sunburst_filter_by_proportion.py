#!/usr/bin/env python3

"""
Use ``ABCA_sunburst_filter_by_proportion.py`` from UNRAVEL to filter ABCA sunburst expression data, keeping prevalent cells at any level (class, subclass, supertype, cluster).

Notes:
    - The proportion threshold means that each cell type must comprise at least 20% of the total cells in sunburst data.
    - Cell types < 20% are filtered out.

Usage:
------
./ABCA_sunburst_filter_by_proportion.py -i path/ABCA_sunburst.csv
"""

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
    opts.add_argument('-t', '--threshold', help='Proportion threshold for filtering. Default: 0.2', default=0.2, type=float, action=SM)
    opts.add_argument('-l', '--level', help='Level to filter on. Default: class', default='class', action=SM)
    opts.add_argument('-o', '--output', help='Output dir path. Default: ABCA_sunburst_proprotion_0.2_supertype', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sunburst_df = pd.read_csv(args.input)

    # Update the percent column in the sunburst_df
    sunburst_df['percent'] = sunburst_df['percent'] / sunburst_df['percent'].sum() * 100

    if args.verbose:
        print('\n[bold]Sunburst data:')
        print(sunburst_df)

    # Calculate the percent for each unique cell
    cell_percent = {}
    unique_cells = sunburst_df[args.level].unique()
    for cell in unique_cells:
        cell_percent[cell] = sunburst_df[sunburst_df[args.level] == cell]['percent'].sum()

    # Make a DataFrame from the cell_percent dictionary
    cell_percent = pd.DataFrame(cell_percent.items(), columns=[args.level, 'percent'])
    cell_percent = cell_percent.sort_values('percent', ascending=False, na_position='last').reset_index(drop=True)

    if args.verbose:
        print('\n[bold]Cell type counts and percent:')
        print(cell_percent)

    # Check if any cell type is > 20% of the total cells
    threshold_percent = args.threshold * 100
    if not (cell_percent['percent'] >= threshold_percent).any():
        print(f"\n[yellow]Error: No cell type is >= {threshold_percent}% of the total cells. Use a lower threshold.")
        return
    
    # Filter out cell types in the sunburst_df that are < 20% of the total cells at the specified level
    sunburst_df_filtered = sunburst_df[
        sunburst_df[args.level].isin(cell_percent[cell_percent['percent'] >= threshold_percent][args.level])
    ]

    # Print unique values in the specified level
    print(f"\nUnique values in the '{args.level}' column with a proportion >= {threshold_percent}%:")
    print(sunburst_df_filtered[args.level].unique())

    # Update the percent column in the sunburst_df_filtered
    sunburst_df_filtered = sunburst_df_filtered.copy()
    sunburst_df_filtered['percent'] = sunburst_df_filtered['percent'] / sunburst_df_filtered['percent'].sum() * 100

    if args.verbose:
        print('\n[bold]Sunburst data after filtering:')
        print(sunburst_df_filtered)

    # Save the filtered results
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(f'ABCA_sunburst_proportion_{args.threshold}_{args.level}')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / str(Path(args.input).name).replace('.csv', f'_proportion.csv')
    sunburst_df_filtered.to_csv(output_path, index=False)
    
    verbose_end_msg()


if __name__ == '__main__':
    main()
