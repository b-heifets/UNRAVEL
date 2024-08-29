#!/usr/bin/env python3

"""
Use ``utils_points_compressor`` from UNRAVEL to pack or unpack point data in a CSV file or summarize the number of points per region.

Input:
    - CSV file with either unpacked (`x, y, z, Region_ID`) or packed (`x, y, z, Region_ID, count`) format.

Output:
    - CSV file with the desired packed or unpacked format.
    - Or save a summary CSV with the number of points per region.

Note:
    - Packing: Group points with the same coordinates and `Region_ID`, adding a `count` column.
    - Unpacking: Expand packed points back to individual rows based on the `count` column.
    - Summary: Output a CSV summarizing the number of points per region.
    - Use only one of the following options: -p, -u, -s.
    - The summary option can be used with either packed or unpacked data.

Usage:
------
    utils_points_compressor -i path/<asterisk>_points.csv [-p or -u or -s] [-v]
"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, process_files_with_glob


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Path to the input CSV file or a glob pattern.", required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-p', '--pack', help="Pack the points by grouping them.", action='store_true')
    opts.add_argument('-u', '--unpack', help="Unpack the points by expanding them based on the `count` column.", action='store_true')
    opts.add_argument('-s', '--summary', help='Output a CSV summarizing the number of points per region.', action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@print_func_name_args_times()
def pack_points(df):
    """
    Pack points by grouping identical coordinates and summing their occurrences.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame with columns ['x', 'y', 'z', 'Region_ID']

    Returns:
    --------
    packed_df : pandas.DataFrame
        DataFrame with columns ['x', 'y', 'z', 'Region_ID', 'count']
    """
    packed_df = df.groupby(['x', 'y', 'z', 'Region_ID']).size().reset_index(name='count')
    return packed_df

@print_func_name_args_times()
def unpack_points(df):
    """
    Unpack points by expanding them based on the `count` column.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame with columns ['x', 'y', 'z', 'Region_ID', 'count']

    Returns:
    --------
    unpacked_df : pandas.DataFrame
        DataFrame with columns ['x', 'y', 'z', 'Region_ID']
    """
    # Repeat rows based on the 'count' column
    unpacked_df = df.loc[df.index.repeat(df['count'])].drop(columns=['count']).reset_index(drop=True)
    return unpacked_df

@print_func_name_args_times()
def summarize_points(df):
    """
    Summarize points by counting the number of points per `Region_ID`.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame with columns ['x', 'y', 'z', 'Region_ID'] or ['x', 'y', 'z', 'Region_ID', 'count']

    Returns:
    --------
    summary_df : pandas.DataFrame
        DataFrame with columns ['Region_ID', 'count'] summarizing the number of points per region.
    """
    if 'count' in df.columns:
        summary_df = df.groupby('Region_ID')['count'].sum().reset_index(name='count')
    else:
        summary_df = df['Region_ID'].value_counts().reset_index()
        summary_df.columns = ['Region_ID', 'count']
    return summary_df

@print_func_name_args_times()
def points_compressor(file_path, pack=False, unpack=False, summary=False):
    """
    Pack, unpack, or summarize points in a CSV file.

    Parameters:
    -----------
    file_path : str
        Path to the input CSV file.
    
    pack : bool, optional
        Pack the points by grouping them.

    unpack : bool, optional
        Unpack the points by expanding them based on the `count` column.

    summary : bool, optional
        Output a CSV summarizing the number of points per region.
    """

    file_path = str(file_path)
    df = pd.read_csv(file_path)
    output_path = None

    if pack:
        if 'count' in df.columns:
            print(f"\n    [red1 bold]Skipping packing:[/] '{file_path}' is already packed.")
            return
        df = pack_points(df)
        output_path = file_path.replace('.csv', '_packed.csv')
    elif unpack:
        if 'count' not in df.columns:
            print(f"\n    [red1 bold]Skipping unpacking:[/] '{file_path}' is already unpacked.")
            return
        df = unpack_points(df)
        output_path = file_path.replace('.csv', '_unpacked.csv')
    elif summary:
        df = summarize_points(df)
        output_path = file_path.replace('.csv', '_summary.csv')
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\n    Points saved to {output_path}\n")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    process_files_with_glob(
        glob_pattern=args.input,
        processing_func=points_compressor,
        pack=args.pack,
        unpack=args.unpack,
        summary=args.summary
    )

    verbose_end_msg()


if __name__ == '__main__':
    main()
