#!/usr/bin/env python3

"""
Use ``_other/drafts/csv_to_nii.py`` from UNRAVEL to convert a CSV file to a NIfTI file.

Outputs:
    - A NIfTI file for each CSV file into a `_csv_to_nii` directory.

Usage:
------
    _other/drafts/csv_to_nii.py -i path/*.csv [-s sort_col] [-val value_cols]
"""

import nibabel as nib
import numpy as np
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="One or more csv paths or glob patterns (space-separated). Default: '*.csv'", default='*.csv', nargs='*', action=SM)
    opts.add_argument('-s', '--sort_col', help='Column to sort by. If used, also use for decoding the NIfTI file.', action=SM)
    opts.add_argument('-val', '--value_cols', help='Column(s) to include in the output NIfTI files. Default: numeric columns other than sort_col.', nargs='*', action=SM)

    return parser.parse_args()

@print_func_name_args_times()
def csv_to_nii(input_pattern='*.csv', sort_col=None, value_cols=None):
    print()
    csv_paths = match_files(input_pattern)
    for csv_path in csv_paths:
        df = pd.read_csv(csv_path)

        if sort_col is not None:
            df = df.sort_values(by=sort_col).reset_index(drop=True)
        else:
            df = df.reset_index(drop=True)

        # Convert the DataFrame (other than the sort_col) to a 2D ndarray
        if value_cols is not None:
            ndarray = df[value_cols].to_numpy()
        else: 
            # Drop the sort_col and non-numeric columns
            ndarray = df.drop(columns=sort_col).select_dtypes(include=[np.number]).to_numpy()

        # Save the ndarray as a NIfTI file
        nii_path = Path('_csv_to_nii', str(csv_path.name).replace('.csv', '.nii.gz'))
        nii_path.parent.mkdir(parents=True, exist_ok=True)
        nii = nib.Nifti1Image(ndarray, np.eye(4))
        nib.save(nii, nii_path)
        print(f"Saved: {nii_path}")

@log_command
def main():
    install()
    args = parse_args()

    csv_to_nii(args.input, args.sort_col, args.value_cols)


if __name__ == '__main__':
    main()