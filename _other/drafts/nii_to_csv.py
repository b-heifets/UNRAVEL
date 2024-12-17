#!/usr/bin/env python3

"""
Use ``_other/drafts/csv_to_nii.py`` from UNRAVEL to convert a NIfTI file to a CSV file.

Usage:
------
    _other/drafts/nii_to_csv.py -i path/img.nii.gz [-c path/file.csv] [-s sort_col] [-col columns] [-o img.csv]
"""

import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.img_io import load_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/img.nii.gz.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--csv_ref', help='path/file.csv matching the NIfTI file for adding a column to the output csv.', default=None, action=SM)
    opts.add_argument('-s', '--sort_col', help='--csv_ref column to sort by (use if used for csv_to_nii.py). After sorting, it is added as the first column.', default=None, action=SM)
    opts.add_argument('-col', '--columns', help='Column name(s) for the output DataFrame.', default=None, nargs='*', action=SM)
    opts.add_argument('-o', '--output', help='Output path. Default: img.csv', default=None, action=SM)

    return parser.parse_args()

@print_func_name_args_times()
def nii_to_csv(nii_path, csv_path=None, sort_col=None, columns=None, output_path=None):
    print()
    ndarray = load_nii(nii_path)
    ndarray_df = pd.DataFrame(ndarray)

    # Name the .nii.gz columns using args.columns
    if columns is not None:
        ndarray_df.columns = columns

    # Merge the DataFrame with the ndarray DataFrame to add the sort_col
    if sort_col is not None and csv_path is not None:
        df = pd.read_csv(csv_path)
        df = df.sort_values(by=sort_col).reset_index(drop=True)
        df = df[sort_col]
        df = df.reset_index(drop=True)
        merged_df = pd.concat([df, ndarray_df], axis=1)
    else:
        merged_df = ndarray_df

    # Save the merged DataFrame as a CSV file
    if output_path is not None: 
        output_csv_path = Path(output_path)
    else:
        output_csv_path = str(Path(nii_path).name).replace('.nii.gz', '.csv')
    merged_df.to_csv(output_csv_path, index=False)
    print(f"Saved: {output_csv_path}")

@log_command
def main():
    install()
    args = parse_args()

    nii_to_csv(args.input, args.csv_ref, args.sort_col, args.columns, args.output)


if __name__ == '__main__':
    main()