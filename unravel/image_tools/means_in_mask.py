#!/usr/bin/env python3

"""
Use ``img_means_in_mask`` or ``means_in_mask`` from UNRAVEL to calculate the mean intensity for each image within a mask.

Usage:
------
    means_in_mask -i path/to/images/*.nii.gz -m path/to/mask.nii.gz [-o mean_in_mask.csv] [-v]
"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.img_io import load_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import initialize_progress_bar, log_command, match_files
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-m', '--mask', help="Path to the mask .nii.gz file.", required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Path to input .nii.gz image(s) or glob pattern(s). Default: '*.nii.gz'.", nargs='*', default=['*.nii.gz'], action=SM)
    opts.add_argument('-o', '--output', help='Output CSV file path. Default: mean_in_mask.csv', default='mean_in_mask.csv', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    nii_files = match_files(args.input)

    mask_file = Path(args.mask)
    mask = load_mask(mask_file)

    n_voxels = mask.sum()
    if n_voxels == 0:
        raise ValueError(f"Mask {mask_file.name} contains no non-zero voxels.")

    rows = []

    progress, task_id = initialize_progress_bar(len(nii_files), "[red]Processing .nii.gz files...")
    with Live(progress):

        for nii in nii_files:
            if args.verbose:
                print(f"\nProcessing image: {nii.name} with mask: {mask_file.name}")

            img = load_nii(nii)

            if img.shape != mask.shape:
                raise ValueError(f"Image and mask shapes do not match for {nii.name} and {mask_file.name}.")

            mean_intensity = img[mask].mean()

            if args.verbose:
                print(f"{nii.name}: Mean intensity in segmented region = {mean_intensity:.2f}")

            rows.append({
                'mask': mask_file.name,
                'image': nii.name,
                'mean_in_mask': mean_intensity
            })

            progress.update(task_id, advance=1)

    df = pd.DataFrame(rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\nResults saved to {output_path}\n")

if __name__ == '__main__':
    main()