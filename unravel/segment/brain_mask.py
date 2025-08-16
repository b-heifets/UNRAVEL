#!/usr/bin/env python3

"""
Use ``seg_brain_mask`` (``sbm``) from UNRAVEL to use a trained ilastik project (pixel classification) to mask the brain in resampled images (for registration or cropping).

Prereqs: 
    - Organize training tif slices (from ``seg_copy_tifs``) into a single folder.
    - Train an Ilastik project to segment the brain (https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project).
    - Train ilastik (tissue = label 1) w/ tifs from reg_inputs/autofl_`*`um_tifs/`*`.tif (from ``reg_prep``)
    - Save brain_mask.ilp for use with -ilp

Inputs: 
    - reg_inputs/autofl_50um.nii.gz from ``reg_prep`` (TIFFs will be loaded from reg_inputs/autofl_50um_tifs)
    - Or any dir with TIFFs (use ``conv`` to convert a 3D image to TIFFs)

Outputs:
    - Same directory as input image.
    - <tif_dir>_ilastik_brain_seg/`*`.tif (TIFF series output from ilastik with labels; label 1 = tissue, all other labels = background)
    - <tif_dir>_brain_mask.nii.gz (can be used for ``reg`` or cropping)
    - <tif_dir>_masked.nii.gz

Note:
    - Ilastik executable files for each OS (update path and version as needed):
    - Linux and WSL: /usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh
    - Mac: /Applications/ilastik-1.4.0.post1-OSX.app/Contents/ilastik-release/run_ilastik.sh
    - Windows: C:\\Program Files\\ilastik-1.4.0.post1\\run_ilastik.bat

Next command: 
    - ``reg`` or ``resample`` to scale the image back to the original resolution to guide cropping.

Usage:
------
    seg_brain_mask -ilp <path/brain_mask.ilp> [-ie path/ilastik_executable ] [-i reg_inputs/autofl_50um.nii.gz] [-d list of paths] [-p sample??] [-v]
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
from unravel.core.utils import get_extension, get_stem, log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-ilp', '--ilastik_prj', help='path/brain_mask.ilp. Default: brain_mask.ilp', default='brain_mask.ilp', action=SM)
    opts.add_argument('-ie', '--ilastik_exe', help='path/ilastik_executable. Default: /usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh', default='/usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh', action=SM)
    opts.add_argument('-i', '--input', help='Path input image to segment (relative to -d folders). Default: reg_inputs/autofl_50um.nii.gz (from ``reg_prep``)', default="reg_inputs/autofl_50um.nii.gz", action=SM)

    opts = parser.add_argument_group('Optional arguments if loading a tif directory')
    opts.add_argument('-x', '--xy_res', help='X and Y resolution in um. Default: None (use image resolution)', default=None, type=float, action=SM)
    opts.add_argument('-z', '--z_res', help='Z resolution in um. Default: None (use image resolution)', default=None, type=float, action=SM)

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
            img_path = sample_path / args.input
            img_stem = get_stem(args.input)
            img_ext = get_extension(img_path)
            brain_mask_output_name = f"{img_stem}_brain_mask.nii.gz"
            brain_mask_output = sample_path / brain_mask_output_name
            img_masked_output_name = f"{img_stem}_masked.nii.gz"
            img_masked_output = sample_path / img_masked_output_name

            # Define the input tif directory for ilastik segmentation
            if img_path.is_dir() and any(img_path.glob('*.tif')):
                tif_dir = str(img_path)
            else:
                tif_dir = str(img_path).replace(img_ext, '_tifs')
                if not Path(tif_dir).exists():
                    print(f"\n\n    {tif_dir} does not exist. Skipping.\n")
                    continue

            # Define the output directory for ilastik segmentation
            seg_dir = f"{tif_dir}_ilastik_brain_seg"

            # Skip if output exists
            if img_masked_output.exists():
                print(f"\n\n    {img_masked_output} already exists. Skipping.\n")
                continue
            
            # Run ilastik segmentation
            if args.ilastik_prj == 'brain_mask.ilp': 
                ilastik_project = Path(sample_path.parent, args.ilastik_prj).resolve()
            else:
                ilastik_project = Path(args.ilastik_prj).resolve()
            pixel_classification(tif_dir, ilastik_project, seg_dir, args.ilastik_exe)

            # Load brain mask image
            seg_img = load_3D_img(seg_dir, "xyz", verbose=args.verbose)

            # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
            brain_mask = np.where(seg_img > 1, 0, seg_img)

            # Load image and resolution
            xy_res = args.xy_res if args.xy_res is not None else None
            z_res = args.z_res if args.z_res is not None else None
            if xy_res is None or z_res is None:
                img, xy_res, z_res = load_3D_img(img_path, return_res=True, verbose=args.verbose)
            else:
                img = load_3D_img(img_path, verbose=args.verbose)

            # Save brain mask as nifti
            save_as_nii(brain_mask, brain_mask_output, xy_res, z_res, np.uint8)

            # Apply brain mask to autofluo image
            autofl_masked = np.where(seg_img == 1, img, 0)

            # Save masked autofl image
            save_as_nii(autofl_masked, img_masked_output, xy_res, z_res, np.uint16)

            # brain_mask(sample, args)
            progress.update(task_id, advance=1)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()