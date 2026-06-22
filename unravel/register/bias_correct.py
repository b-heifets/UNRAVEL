#!/usr/bin/env python3

"""
Use ``reg_bias_correct`` or ``bias_corr`` from UNRAVEL to apply N4 bias field correction to an .nii.gz image.

Note:
    - No padding or registration is performed.

Usage:
------
bias_corr -i <template.nii.gz> -o <output.nii.gz> [-mas <mask.nii.gz>] [-v]
"""

import ants
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import save_as_nii
from unravel.core.utils import log_command
from unravel.register.reg import bias_correction


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", required=True, help="Input image.nii.gz", action=SM)
    reqs.add_argument("-o", "--output", required=True, help="Output bias-corrected image.nii.gz", action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument( "-mas", "--mask", help="Optional brain mask for bias correction. Default: None", default=None, action=SM)
    opts.add_argument( "-sf", "--shrink_factor", help="Shrink factor for N4 bias correction. Default: 2", type=int, default=2, action=SM )

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", action="store_true", default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    print(f"\n[bold]Bias correcting template:[/bold] {input_path.name}")

    if args.mask is None or args.mask == "None":
        img_bias_corrected = bias_correction(str(input_path), mask_path=None, shrink_factor=args.shrink_factor, verbose=args.verbose)
    else:
        mask_path = Path(args.mask)
        if not mask_path.exists():
            raise FileNotFoundError(f"Mask not found: {mask_path}")
        img_bias_corrected = bias_correction(str(input_path), mask_path=str(mask_path), shrink_factor=args.shrink_factor, verbose=args.verbose)

    # Convert back to NIfTI
    output_path = Path(args.output)
    save_as_nii(img_bias_corrected, output_path, reference=input_path)

if __name__ == "__main__":
    main()
