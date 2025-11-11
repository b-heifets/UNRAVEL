#!/usr/bin/env python3
"""
Use ``nrrd_to_nii.py`` from UNRAVEL to convert .nrrd files to .nii.gz.

Usage:
------
    `nrrd_to_nii.py -r reference.nii.gz [-i 'data/*.nrrd'] [-o output_dir/:_suffix] [-d float32] [-v]`
"""

import nrrd
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, print_func_name_args_times, resolve_output_paths, verbose_start_msg, verbose_end_msg
from unravel.core.img_io import save_as_nii


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-r', '--ref_nii', help='Path to reference .nii.gz for header and affine info.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Input .nrrd path(s) or pattern(s). Default: '*.nrrd'", default="*.nrrd", nargs="*", action=SM)
    opts.add_argument('-o', '--output', help="Output file, dir, suffix, or dir with suffix (e.g., 'out_dir/:_suffix' → out_dir/input_suffix.nii.gz).", action=SM)
    opts.add_argument('-d', '--dtype', help='Data type for output NIfTI (e.g., float32, uint16). Default: float32', default='float32', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help="Increase verbosity. Default: False", action="store_true", default=False)
    return parser.parse_args()

@print_func_name_args_times()
def nrrd_to_nii(nrrd_path: str | Path, output_path: str | Path, ref_nii_path: str | Path, dtype=None):
    """Convert a single .nrrd file to .nii.gz format using reference metadata."""
    nrrd_path = Path(nrrd_path)
    img, header = nrrd.read(nrrd_path)
    save_as_nii(img, output_path, reference=ref_nii_path, data_type=dtype)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_paths = match_files(args.input)
    output_paths = resolve_output_paths(file_paths=input_paths, output_paths=args.output, ext=".nii.gz")

    for in_path, out_path in zip(input_paths, output_paths):
        nrrd_to_nii(in_path, out_path, ref_nii_path=args.ref_nii, dtype=args.dtype)

    verbose_end_msg()


if __name__ == "__main__":
    main()
