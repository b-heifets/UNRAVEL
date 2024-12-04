#!/usr/bin/env python3

"""
Use ``_other/drafts/csv_to_nii.py`` from UNRAVEL to convert a NIfTI file to a CSV file.

Outputs:
    - A CSV file for each NIfTI file into a `_nii_to_csv` directory.

Notes:
    - Use the same .nii.gz file pattern and working dir for this script and for the "csv_to_nii.py" script.
    - If sort_col is used, it will be added as the first column in the output csv.
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

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='path/*.csv. Default: *.csv', default='*.csv', action=SM)
    opts.add_argument('-s', '--sort_col', help='Column to sort by. If used, also use for decoding the NIfTI file.', action=SM)
    opts.add_argument('-c', '--columns', help='Column name(s) for the output DataFrame. Default: None', nargs='*', action=SM)

    return parser.parse_args()

@print_func_name_args_times()
def nii_to_csv(input_pattern='*.nii.gz', sort_col=None, columns=None):
    print()
    csv_paths = [Path(file) for file in glob(input_pattern)]
    for csv_path in csv_paths:
        # Load the NIfTI file and convert it back to a DataFrame
        nii_path = Path('_csv_to_nii', str(csv_path.name).replace('.csv', '.nii.gz'))
        ndarray = load_nii(nii_path)
        ndarray_df = pd.DataFrame(ndarray)

        # Name the columns using args.columns
        if columns is not None:
            ndarray_df.columns = columns

        # Merge the DataFrame with the ndarray DataFrame
        if sort_col is not None:
            df = pd.read_csv(csv_path)
            df = df.sort_values(by=sort_col).reset_index(drop=True)
            df = df[sort_col]
            df = df.reset_index(drop=True)
            merged_df = pd.concat([df, ndarray_df], axis=1)
        else:
            merged_df = ndarray_df

        # Save the merged DataFrame as a CSV file
        Path('_nii_to_csv').mkdir(exist_ok=True)
        csv_path = Path('_nii_to_csv', str(csv_path.name))
        merged_df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")

@log_command
def main():
    install()
    args = parse_args()

    nii_to_csv(args.input, args.sort_col, args.columns)


if __name__ == '__main__':
    main()