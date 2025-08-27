#!/usr/bin/env python3

"""
Use ``img_avg`` (``avg``) from UNRAVEL to average NIfTI images.

Usage:
------
    img_avg -i "<asterisk>.nii.gz" -o avg.nii.gz [-v]
"""

import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Input file(s) or pattern(s) to process. Default is '*.nii.gz'.",  nargs='*', default='*.nii.gz', action=SM)
    opts.add_argument('-o', '--output', help='Output file name. Default is "avg.nii.gz".', default='avg.nii.gz', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Make output dirs if they don't exist

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Resolve file patterns to actual file paths
    file_paths = match_files(args.input)

    print(f'\n    Averaging: {str(file_paths)}\n')

    # Initialize sum array and affine matrix
    sum_image = None
    affine = None

    # Process each file
    for file_path in file_paths:
        nii = nib.load(str(file_path))
        if sum_image is None:
            sum_image = np.asanyarray(nii.dataobj, dtype=np.float64).squeeze()  # Use float64 to avoid overflow
            affine = nii.affine
            header = nii.header
            data_type = nii.header.get_data_dtype()
        else:
            sum_image += np.asanyarray(nii.dataobj, dtype=np.float64).squeeze()
    

    # Calculate the average
    average_image = sum_image / len(file_paths)

    # Save the averaged image
    averaged_nii = nib.Nifti1Image(average_image, affine, header)
    averaged_nii.set_data_dtype(data_type)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    nib.save(averaged_nii, output)
    print(f"    Saved {output}\n")

    verbose_end_msg()
    

if __name__ == '__main__':
    main()