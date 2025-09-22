#!/usr/bin/env python3

"""
Use ``warp_points_to_atlas`` (``wp2a``) from UNRAVEL to convert cell centroids in native space to an image matching the fixed registration input and then warp it to atlas space.


Prereqs: 
    ``reg`` and ``rstats``

Inputs:
    - regional_stats/<Condition>_sample??_cell_centroids.csv (w/ columns: x, y, z, Region_ID) from ``rstats`` (first glob match processed)
    - Reference image for target shape for converting points to image before padding and warping: reg_inputs/autofl_50um.nii.gz from ``reg_prep``
    - Reference image for warping to atlas space: e.g., atlas/atlas_CCFv3_2020_30um.nii.gz

Outputs:
    - ./sample??/atlas_space/<input>.nii.gz

Notes:
    - If the input CSV has a 'count' column, use ``utils_points_compressor`` to unpack the points before running this script.

Usage:
------
    warp_points_to_atlas -i regional_stats/<asterisk>_sample??_cell_centroids.csv [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-fri reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz] [-af reg_inputs/autofl_50um.nii.gz] [-thr 20000 or -uthr 20000] [-md parameters/metadata.txt] [-mi] [-d list of paths] [-p sample??] [-v]
"""

import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_image_metadata_from_txt, nii_to_ndarray, nii_voxel_size
from unravel.core.img_tools import reorient_axes, reverse_reorient_axes
from unravel.core.utils import get_pad_percent, log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples
from unravel.image_io.img_to_points import img_to_points
from unravel.image_tools.resample_points import resample_and_convert_points
from unravel.warp.to_atlas import to_atlas


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='regional_stats/<Condition>_sample??_cell_centroids.csv (w/ columns: x, y, z, Region_ID) from ``rstats`` (first glob match processed)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-a', '--atlas', help='path/atlas.nii.gz or template matching moving image (Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-af', '--autofl_img', help='reg_inputs/autofl_50um.nii.gz from ``reg_prep`` (reference for `resample_and_convert_points()`)', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    opts.add_argument('-thr', '--thresh', help='Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data)', type=float, action=SM)
    opts.add_argument('-uthr', '--upper_thr', help='Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data)', type=float, action=SM)
    opts.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Padding percentage from ``reg``. Default: from parameters/pad_percent.txt or 0.25.', type=float, action=SM)
    opts.add_argument('-o', '--output', help='Output directory for atlas space images relative to sample??/. Default: atlas_space', default=None, action=SM)
    opts.add_argument('-op', '--output_points', help='Output directory for resampled points csv relative to sample??/. Default: reg_inputs/points', default=None, action=SM)

    compatability = parser.add_argument_group('Compatability options')
    compatability.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting). Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()
            current_res = (xy_res, xy_res, z_res)

            # Load the csv with cell centroids in full resolution tissue space
            csv_path = next(sample_path.glob(str(args.input)), None)
            if csv_path is None:
                print(f"\n\n    [red1]No CSV file found in {sample_path} matching {args.input}. Skipping.\n")
                continue

            # Define main output path
            output_dir = sample_path / "atlas_space" if args.output is None else sample_path / args.output
            output_dir.mkdir(exist_ok=True, parents=True)
            output_img_path = output_dir / str(csv_path.name).replace(".csv", ".nii.gz")
            output_img_path.parent.mkdir(exist_ok=True, parents=True)
            if output_img_path.exists():
                print(f"\n\n    {output_img_path} already exists. Skipping.\n")
                continue

            # Load reg_inputs/autofl_50um.nii.gz from ``reg_prep`` for shape and target resolution
            autofl_path = sample_path / args.autofl_img
            autofl_nii = nib.load(autofl_path)
            ref_img = nii_to_ndarray(autofl_nii)
            target_res = nii_voxel_size(autofl_nii)

            # Optionally reorient autofluo image
            if args.miracl:  # autofl_nii = clar_allen_reg/clar_res0.05.nii.gz
                ref_img = reverse_reorient_axes(ref_img)

            # Resample and convert points to an image matching reg_inputs/autofl_50um.nii.gz
            _, points_resampled_img = resample_and_convert_points(csv_path, current_res, target_res, ref_img, args.thresh, args.upper_thr)

            # Optionally reorient autofluo image (mimics MIRACL's tif to .nii.gz conversion)
            if args.miracl: 
                points_resampled_img = reorient_axes(points_resampled_img)

            # Convert the resampled image to a points DataFrame
            points_resampled_ndarray = img_to_points(points_resampled_img)
            points_resampled_df = pd.DataFrame(points_resampled_ndarray, columns=['x', 'y', 'z'])

            # Save the resampled points to a CSV file
            csv_output_path = sample_path / args.output_points / str(csv_path.name) if args.output_points is not None else sample_path / "reg_inputs" / "points" / str(csv_path.name)
            csv_output_path.parent.mkdir(exist_ok=True, parents=True)
            points_resampled_df.to_csv(csv_output_path, index=False)
            print(f"\n    Points saved to: {csv_output_path}\n")

            # Warp native image to atlas space (Padded warp() input image with points saved to <reg_outputs>/warp_inputs/<output>.nii.gz)
            if np.max(points_resampled_img) > 0:
                dtype = 'uint16' if np.max(points_resampled_img) > 255 else 'uint8'
        
            pad_percent = get_pad_percent(sample_path / Path(args.fixed_reg_in).parent, args.pad_percent)
            to_atlas(sample_path, points_resampled_img, args.fixed_reg_in, args.atlas, output_img_path, 'nearestNeighbor', dtype=dtype, pad_percent=pad_percent)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()