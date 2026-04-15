#!/usr/bin/env python3

"""
Use ``_other/drafts/2D/mean_in_seg.py`` from UNRAVEL to calculate the mean intensity of a 2D image within a segmentation mask.

Note:
    - Pattern matches are sorted, whereas explicit paths are used as-is.
    - So if you provide a glob pattern for the input image and mask, make sure they sort in the same order (e.g., img_001.tif, img_002.tif and img_001_mask.tif, img_002_mask.tif).

Usage:
------
    _other/drafts/2D/mean_in_seg.py -i path/*.tif -m path/*_mask.tif [-f 1] [-o mean_in_seg.csv] [-v]
"""

import pandas as pd
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.img_io import load_single_tif
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Path to input tif(s) or glob pattern (e.g., '*.tif').", nargs='*', required=True, action=SM)
    reqs.add_argument('-m', '--mask', help="Path to the mask tif(s) or glob pattern (e.g., '*.tif').", nargs='*', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-f', '--foreground-value', help='Pixel value in the mask that indicates the foreground (segmented region). Default: 1', default=1, type=int, action=SM)
    opts.add_argument('-o', '--output', help='Output CSV file path. Default: mean_in_seg.csv', default='mean_in_seg.csv', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    tif_files = match_files(args.input)
    if args.verbose:
        tif_names = [ Path(tif).name for tif in tif_files ]
        print(f"Input image files: {tif_names}")

    mask_files = match_files(args.mask)
    if args.verbose:
        mask_names = [ Path(mask).name for mask in mask_files ]
        print(f"Mask files: {mask_names}")

    if len(mask_files) != len(tif_files):
        raise ValueError(f"Number of mask files must match the number of input tif files. Inputs: {len(tif_files)}, Masks: {len(mask_files)}")
    
    rows = []

    for tif_file, mask_file in zip(tif_files, mask_files):
        print(f"\nProcessing image: {tif_file.name} with mask: {mask_file.name}")

        img = load_single_tif(tif_file)
        mask = load_single_tif(mask_file)

        if img.shape != mask.shape:
            raise ValueError(f"Image and mask shapes do not match for {tif_file.name} and {mask_file.name}.")

        if args.verbose:
            print(f"Unique mask values: {np.unique(mask)}")

        seg = (mask == args.foreground_value)

        if not seg.any():
            raise ValueError(
                f"No pixels with foreground value {args.foreground_value} were found in mask: {mask_file.name}"
            )

        mean_intensity = img[seg].mean()
        print(f"{tif_file.name}: Mean intensity in segmented region = {mean_intensity:.2f}")

        rows.append({
            'image': tif_file.name,
            'mask': mask_file.name,
            'mean_in_seg': mean_intensity
        })

    df = pd.DataFrame(rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\nResults saved to {output_path}\n")

if __name__ == '__main__':
    main()