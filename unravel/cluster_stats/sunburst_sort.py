#!/usr/bin/env python3

"""
Use ``cstats_sunburst_sort`` (``sunburst_sort``) from UNRAVEL to sort sunburst CSVs by hierarchy and value.

Prereqs:
    - ``cstats_sunburst``, ``cstats_index``, ``cstats_summary``, or ``abca_sunburst``, etc. to generate sunburst CSVs.

Inputs:
    - CSVs with sunburst data (the name should end with sunburst.csv)

Outputs:
    - A hierarchically sorted CSV: _sorted_sunburst_CSVs/<input_file_name>_sunburst_sorted.csv

Sorting by hierarchy and value:
--------------------------------
Group by Depth: Starting from the earliest depth column, for each depth level:
   - Sum the values of all rows sharing the same region (or combination of regions up to that depth).
   - Sort these groups by their aggregate value in descending order, ensuring larger groups are prioritized.

Sort Within Groups: Within each group created in step 1:
   - Sort the rows by their individual value in descending order.

Maintain Grouping Order:
   - As we move to deeper depth levels, maintain the grouping and ordering established in previous steps (only adjusting the order within groups based on the new depth's aggregate values).

Usage:
------
    cstats_sunburst_sort [-i <input_files>] [-v]
"""


import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-i', '--input', help="One or more sunburst CSV paths or glob patterns (space-separated). Default: '*.csv'", default='*.csv', nargs='*', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def sunburst_sort(df, value_column=None, depth_columns=None):
    """
    Sort a sunburst hierarchy while preserving parent-group contiguity.

    Rows are ordered so that:
      1. top-level groups are ordered by summed value
      2. within each parent group, child groups are ordered by summed value
      3. leaf rows are ordered by individual value

    For ragged hierarchies, missing depth values are temporarily filled across
    columns within each row for grouping, then restored from the original table
    before returning.
    """
    df_original = df.copy()

    if value_column is None:
        value_column = df.columns[-1]

    if depth_columns is None:
        depth_columns = [c for c in df.columns if c != value_column]

    df_work = df.copy()

    # For ragged hierarchies, fill across columns within each row so grouping works.
    df_work[depth_columns] = df_work[depth_columns].replace('', pd.NA)

    if df_work[depth_columns].isnull().any().any():
        df_work[depth_columns] = df_work[depth_columns].ffill(axis=1)

    def sort_block(block, level):
        # Base case: no deeper hierarchy left
        if level >= len(depth_columns):
            return block.sort_values(value_column, ascending=False, kind='stable')

        col = depth_columns[level]

        # Order children within this parent block by summed value
        child_order = (
            block.groupby(col, dropna=False, sort=False)[value_column]
            .sum()
            .sort_values(ascending=False, kind="stable")
            .index
        )

        parts = []
        for child in child_order:
            child_block = block[block[col].eq(child)]
            parts.append(sort_block(child_block, level + 1))

        return pd.concat(parts, axis=0)

    df_sorted = sort_block(df_work, 0)

    # Use the index to replace filled values with original ones where NaN existed
    df_restored = df_sorted.copy()
    for col in depth_columns:
        df_restored[col] = df_original.loc[df_restored.index, col]

    return df_restored


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    csv_paths = match_files(args.input)

    for csv_path in csv_paths:
        if args.verbose:
            print(f"\nProcessing: {csv_path}\n")

        sunburst_csv_path = Path(csv_path)

        df = pd.read_csv(sunburst_csv_path, keep_default_na=False)

        # Sort the DataFrame by hierarchy and volume
        df_sorted = sunburst_sort(df)

        # Save the sorted DataFrame to a new CSV file
        sorted_parent_path = sunburst_csv_path.parent / '_sorted_sunburst_CSVs'
        sorted_parent_path.mkdir(parents=True, exist_ok=True)
        if sunburst_csv_path.name.endswith('sunburst.csv'):
            sorted_csv_name = str(sunburst_csv_path.name).replace('sunburst.csv', 'sunburst_sorted.csv')
        else:
            sorted_csv_name = sunburst_csv_path.stem + '_sorted.csv'
        df_sorted.to_csv(sorted_parent_path / sorted_csv_name, index=False)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()