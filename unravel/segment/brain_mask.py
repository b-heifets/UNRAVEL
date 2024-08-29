#!/usr/bin/env python3

"""
Use ``seg_brain_mask`` from UNRAVEL to use a trained ilastik project (pixel classification) to mask the brain in resampled autofluo images (often improves registration).

Prereqs: 
    - Organize training tif slices (from ``seg_copy_tifs``) into a single folder.
    - Train an Ilastik project to segment the brain (https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project).
    - Train ilastik (tissue = label 1) w/ tifs from reg_inputs/autofl_<asterisk>um_tifs/<asterisk>.tif (from ``reg_prep``)
    - Save brain_mask.ilp in experiment directory of use -ilp

Inputs: 
    - reg_inputs/autofl_<asterisk>um.nii.gz
    - brain_mask.ilp # in exp dir

Outputs: 
    - reg_inputs/autofl_<asterisk>um_tifs_ilastik_brain_seg/slice_<asterisk>.tif series
    - reg_inputs/autofl_<asterisk>um_brain_mask.nii.gz (can be used for ``reg`` and ``vstats_z_score``)
    - reg_inputs/autofl_<asterisk>um_masked.nii.gz

Next command: 
    - ``reg``

Usage:
------
    seg_brain_mask -ie <path/ilastik_executable> -ilp <path/brain_mask.ilp> [-i reg_inputs/autofl_50um.nii.gz] [-d list of paths] [-p sample??] [-v]
"""

import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.img_io import load_3D_img, resolve_path, save_as_nii
from unravel.core.img_tools import pixel_classification
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-ie', '--ilastik_exe', help='path/ilastik_executable.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-ilp', '--ilastik_prj', help='path/brain_mask.ilp. Default: brain_mask.ilp', default='brain_mask.ilp', action=SM)
    opts.add_argument('-i', '--input', help='Resampled autofluo image. Default: reg_inputs/autofl_50um.nii.gz (from ``reg_prep``)', default="reg_inputs/autofl_50um.nii.gz", action=SM)

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

            # Define input and output paths
            autofl_img_path = resolve_path(sample_path, path_or_pattern=args.input)
            brain_mask_output = Path(str(autofl_img_path).replace('.nii.gz', '_brain_mask.nii.gz'))
            autofl_img_masked_output = Path(str(autofl_img_path).replace('.nii.gz', '_masked.nii.gz'))
            autofl_tif_directory = str(autofl_img_path).replace('.nii.gz', '_tifs')
            seg_dir = f"{autofl_tif_directory}_ilastik_brain_seg"

            # Skip if output exists
            if autofl_img_masked_output.exists():
                print(f"\n\n    {autofl_img_masked_output} already exists. Skipping.\n")
                continue
            
            # Run ilastik segmentation
            if args.ilastik_prj == 'brain_mask.ilp': 
                ilastik_project = Path(sample_path.parent, args.ilastik_prj).resolve()
            else:
                ilastik_project = Path(args.ilastik_prj).resolve()
            pixel_classification(autofl_tif_directory, ilastik_project, seg_dir, args.ilastik_exe)

            # Load brain mask image
            seg_img = load_3D_img(seg_dir, "xyz")

            # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
            brain_mask = np.where(seg_img > 1, 0, seg_img)

            # # Load autofl image
            autofl_img, xy_res, z_res = load_3D_img(autofl_img_path, return_res=True)

            # Save brain mask as nifti
            save_as_nii(brain_mask, brain_mask_output, xy_res, z_res, np.uint8)

            # Apply brain mask to autofluo image
            autofl_masked = np.where(seg_img == 1, autofl_img, 0)

            # Save masked autofl image
            save_as_nii(autofl_masked, autofl_img_masked_output, xy_res, z_res, np.uint16)

            # brain_mask(sample, args)
            progress.update(task_id, advance=1)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()