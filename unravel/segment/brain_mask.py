#!/usr/bin/env python3

"""
Use ``seg_brain_mask`` (``sbm``) from UNRAVEL to use a trained ilastik project (pixel classification) to mask the brain in resampled images (for registration or cropping).

Prereqs: 
    - Organize training tif slices (from ``seg_copy_tifs``) into a single folder.
    - Train an Ilastik project to segment the brain (https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project).
    - Train ilastik (tissue = label 1) w/ tifs from reg_inputs/autofl_`*`um_tifs/`*`.tif (from ``reg_prep``)
    - Save brain_mask.ilp for use with -ilp

Inputs: 
    - reg_inputs/autofl_50um.nii.gz from ``reg_prep`` (Non-TIFF inputs will be converted to TIFFs for ilastik).
    - Or any dir with TIFFs

Outputs:
    - Same directory as input image.
    - <tif_dir>_ilastik_brain_seg/`*`.tif (TIFF series output from ilastik with labels; label 1 = tissue, all other labels = background)
    - <tif_dir>_brain_mask.nii.gz (can be used for ``reg`` or cropping)
    - <tif_dir>_masked.nii.gz (use for ``reg``; Use -bmo to skip generating the masked image [not needed for cropping]).

Note:
    - Ilastik executable files for each OS (update path and version as needed):
    - Linux and WSL: /usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh
    - Mac: /Applications/ilastik-1.4.0.post1-OSX.app/Contents/ilastik-release/run_ilastik.sh
    - Windows: C:\\Program Files\\ilastik-1.4.0.post1\\run_ilastik.bat

Next command: 
    - ``reg`` or ``resample`` to scale the image back to the original resolution to guide cropping.

Usage to prep for ``reg``:
--------------------------
    seg_brain_mask -ilp <path/brain_mask.ilp> [-i reg_inputs/autofl_50um.nii.gz] [-ie path/ilastik_executable ] [-d list of paths] [-p sample??] [-v]

Usage for cropping Genetic Tools Atlas (GTA) images:
----------------------------------------------------
    seg_brain_mask -ilp <path/brain_mask.ilp> -i prep_brain_mask -x 112 -z 100 -o brain_mask.nii.gz -bmo -p 'ID_*' [-v]
"""

import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.img_io import load_3D_img, resolve_path, save_as_nii, save_as_tifs
from unravel.core.img_tools import pixel_classification
from unravel.core.utils import get_extension, get_stem, log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-ilp', '--ilastik_prj', help='path/brain_mask.ilp.', required=True, action=SM)

    key_args = parser.add_argument_group('Optional arguments')
    key_args.add_argument('-ie', '--ilastik_exe', help='path/ilastik_executable. Default: /usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh', default='/usr/local/ilastik-1.4.0.post1-Linux/run_ilastik.sh', action=SM)
    key_args.add_argument('-i', '--input', help='Path input image to segment (relative to -d folders). Default: reg_inputs/autofl_50um.nii.gz (from ``reg_prep``)', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    key_args.add_argument('-o', '--output', help='path/brain_mask.nii.gz. Default: <input_image>_brain_mask.nii.gz', default=None, action=SM)
    key_args.add_argument('-bmo', '--brain_mask_only', help='Only generate brain_mask.nii.gz (skip img_masked.nii.gz). Default: False', action='store_true')

    opts_conv = parser.add_argument_group('Optional arguments for conversion to tif series')
    opts_conv.add_argument('-c', '--channel', help='Channel number for image loading if applicable. Default: 0', default=0, type=int, action=SM)

    opts_res = parser.add_argument_group('Optional arguments for output resolution (if -i is a tif series)')
    opts_res.add_argument('-x', '--xy_res', help='X and Y resolution in um. Default: None (use -i img.nii.gz resolution)', default=None, type=float, action=SM)
    opts_res.add_argument('-z', '--z_res', help='Z resolution in um. Default: None (use -i img.nii.gz resolution)', default=None, type=float, action=SM)

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
            if args.output is None:
                brain_mask_output_name = f"{img_stem}_brain_mask.nii.gz"
                brain_mask_output = sample_path / brain_mask_output_name
            else:
                brain_mask_output = sample_path / args.output

            if not args.brain_mask_only:
                img_masked_output_name = f"{img_stem}_masked.nii.gz"
                img_masked_output = sample_path / img_masked_output_name

            # Decide which file to check for skipping
            skip_output = brain_mask_output if args.brain_mask_only else img_masked_output
            if skip_output.exists():
                print(f"\n\n    {skip_output} already exists. Skipping.\n")
                continue

            # Define tif directory and, if necessary, convert the input image to a tif series
            if img_path.is_dir() and any(img_path.glob('*.tif')):
                tif_dir = str(img_path)
            elif img_ext in ['.tif', '.ome.tif'] and len(Path(img_path.parent).glob('*.tif')) > 1:  # A file from the tif series was provided
                tif_dir = str(img_path.parent)
            else:
                tif_dir = img_path.parent / f"{img_stem}_tifs"
                if not tif_dir.exists() and img_path.is_file():
                    # Load the input image and convert to tif series for ilastik segmentation
                    img = load_3D_img(img_path, channel=args.channel, verbose=args.verbose)
                    tif_dir.mkdir(parents=True, exist_ok=True)
                    save_as_tifs(img, tif_dir, verbose=args.verbose)

            # Define the output directory for ilastik segmentation
            seg_dir = Path(str(tif_dir).rstrip('_tifs')) / 'ilastik_brain_seg'
            
            # Run ilastik segmentation
            ilastik_project = Path(args.ilastik_prj).resolve()
            pixel_classification(tif_dir, ilastik_project, seg_dir, args.ilastik_exe)

            # Load brain mask image
            seg_img = load_3D_img(seg_dir, "xyz", verbose=args.verbose)

            # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
            brain_mask = np.where(seg_img > 1, 0, seg_img)

            # Load image and resolution
            xy_res, z_res = args.xy_res, args.z_res
            if xy_res is None or z_res is None:
                img, xy_res, z_res = load_3D_img(img_path, return_res=True, verbose=args.verbose)
            else:
                img = load_3D_img(img_path, verbose=args.verbose)

            # Save brain mask as nifti
            save_as_nii(brain_mask, brain_mask_output, xy_res, z_res, np.uint8)

            if not args.brain_mask_only:
                # Apply brain mask to autofluo image
                autofl_masked = np.where(seg_img == 1, img, 0)
                save_as_nii(autofl_masked, img_masked_output, xy_res, z_res, np.uint16)

            progress.update(task_id, advance=1)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()