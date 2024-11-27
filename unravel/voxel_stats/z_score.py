#!/usr/bin/env python3

"""
Use ``vstats_z_score`` (``zs``) from UNRAVEL to z-score an atlas space image using a tissue mask and/or an atlas mask.

Prereqs:
    ``vstats_prep`` for inputs [& ``seg_brain_mask`` for tissue masks]

Inputs:
    - atlas_space/<askterisk>_image.nii.gz relative to sample??
    - reg_inputs/autofl_50um_brain_mask.nii.gz (optional)
    - path/to/atlas_mask.nii.gz (optional)

Outputs:
    - <path/input_img>_z.nii.gz (float32) saved in the same directory as the input image. 

Note:
    - z-score = (img.nii.gz - mean pixel intensity in brain)/standard deviation of intensity in brain

Next commands for voxel-wise stats: 
    - Aggregate atlas space IF images with ``utils_agg_files``.
    - If analyzing whole brains, consider using ``vstats_whole_to_avg`` to average left and right hemispheres.
    - If using side-specific z-scoring, use ``vstats_hemi_to_avg`` to average the images.
    - Prepend condition names with ``utils_prepend``.
    - Check images in FSLeyes and run ``vstats`` to perform voxel-wise stats.

Usage:
------
    vstats_z_score -i rel_path/img.nii.gz [--suffix z] [--tissue_mask reg_inputs/autofl_50um_brain_mask.nii.gz] [-amas path/atlas_mask.nii.gz] [-fri reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz] [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-d list of paths] [-p sample??] [-v]

Usage w/ an atlas mask:
-----------------------
    vstats_z_score -i 'path/<asterisk>.nii.gz' -amas path/atlas_mask.nii.gz

Usage w/ a tissue mask:
-----------------------
    vstats_z_score -i 'atlas_space/<asterisk>.nii.gz' -tmas reg_inputs/autofl_50um_brain_mask.nii.gz -a atlas/atlas_CCFv3_2020_30um.nii.gz

Usage w/ both masks for side-specific z-scoring:
------------------------------------------------
    vstats_z_score -i 'atlas_space/<asterisk>.nii.gz' -tmas reg_inputs/autofl_50um_brain_mask.nii.gz -amas path/RH_mask.nii.gz -s RH_z --dirs <list of paths>
"""

import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import get_pad_percent, log_command, verbose_start_msg, verbose_end_msg, get_samples, initialize_progress_bar, print_func_name_args_times
from unravel.warp.to_atlas import to_atlas


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the image(s) to be z-scored relative to the current dir or sample?? dirs (glob matches processed)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--suffix', help='Output suffix. Default: z (.nii.gz replaced w/ _z.nii.gz)', default='z', action=SM)

    tissue_mask_opts = parser.add_argument_group('Optional args for using a tissue mask')
    tissue_mask_opts.add_argument('-tmas', '--tissue_mask', help='rel_path/brain_mask.nii.gz. For example, reg_inputs/autofl_50um_brain_mask.nii.gz', default=None, action=SM)
    tissue_mask_opts.add_argument('-fri', '--fixed_reg_in', help='Fixed image from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    tissue_mask_opts.add_argument('-a', '--atlas', help='path/atlas.nii.gz. It is used as a reference image for warping the tissue mask to atlas space. Default: atlas/atlas_CCFv3_2020_30um.nii.gz', default=None, action=SM)
    tissue_mask_opts.add_argument('-pad', '--pad_percent', help='Padding percentage from ``reg``. Default: from parameters/pad_percent.txt or 0.15.', type=float, action=SM)

    atlas_mask_opts = parser.add_argument_group('Optional args for using an atlas mask')
    atlas_mask_opts.add_argument('-amas', '--atlas_mask', help='path/atlas_mask.nii.gz (can use tmas and/or amas)', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', default=False, action='store_true')

    return parser.parse_args()

# TODO: Set voxels outside the mask(s) to zero


@print_func_name_args_times()
def z_score(input_nii_path, mask_img, suffix):
    """Z-score a .nii.gz using a mask ndarray and save the output as a float32 .nii.gz.
    
    Parameters:
        - img (str): the ndarray to be z-scored.
        - mask (str): the brain mask ndarray
        - suffix (str): the suffix to append to the output filename
        
    Outputs:
        - img_z.nii.gz (float32)
        
    Returns:
        - z_scored_img (np.ndarray): the z-scored image"""
    
    if not Path(input_nii_path).exists():
        raise FileNotFoundError(f"\n    [red1]Input image not found: {input_nii_path}\n")

    nii = nib.load(input_nii_path)
    img = np.asanyarray(nii.dataobj, dtype=np.float32).squeeze()

    # Zero out voxels outside the mask
    masked_data = img * mask_img

    # Calculate mean and standard deviation for masked data
    masked_nonzero = masked_data[masked_data != 0]  # Exclude zero voxels

    mean_intensity = masked_nonzero.mean()
    std_dev = masked_nonzero.std()

    # Z-score calculation
    z_scored_img = (masked_data - mean_intensity) / std_dev

    # Set voxels outside the mask to zero
    # z_scored_img *= mask

    # Save the z-scored image
    output_path = Path(str(input_nii_path).replace('.nii.gz', f'_{suffix}.nii.gz'))
    nii.header.set_data_dtype(np.float32)
    z_scored_nii = nib.Nifti1Image(z_scored_img, nii.affine, nii.header)
    nib.save(z_scored_nii, output_path)

    return z_scored_img

def tissue_mask_to_atlas_space(sample_path, tissue_mask_path, fixed_reg_input, atlas_path, pad_percent=0.15, verbose=False):
    """Warp a tissue mask to atlas space (e.g., for z-scoring).
    
    Parameters:
        - sample_path (Path): Path to the sample directory.
        - tissue_mask_path (Path): Path to the tissue mask.
        - fixed_reg_input (str): Name of the fixed image for registration.
        - atlas_path (str): Path to the atlas.

    Returns:
        - tissue_mask_img (np.ndarray): the tissue mask in atlas space.
    """

    tissue_mask_nii_output = sample_path / "atlas_space" / Path(tissue_mask_path).name

    if not Path(tissue_mask_nii_output).exists():
        brain_mask_in_tissue_space = load_3D_img(tissue_mask_path, verbose=verbose)
        to_atlas(sample_path, brain_mask_in_tissue_space, fixed_reg_input, atlas_path, tissue_mask_nii_output, 'multiLabel', dtype='float32', pad_percent=pad_percent)  # or 'nearestNeighbor'

    tissue_mask_img = load_3D_img(tissue_mask_nii_output, verbose=verbose)
    tissue_mask_img = np.where(tissue_mask_img > 0, 1, 0).astype(np.uint8)
    return tissue_mask_img

def z_score_mask(sample_path, input_path, fixed_reg_input, atlas_path, tissue_mask_path=None, atlas_mask_path=None, pad_percent=0.15, verbose=False):
    """Combine tissue and atlas masks if both are provided, otherwise use whichever is available.
    
    Parameters:
        - sample_path (Path): Path to the sample directory.
        - input_path (Path): Path to the image to be z-scored.
        - fixed_reg_input (str): Name of the fixed image for registration.
        - atlas_path (str): Path to the atlas.
        - tissue_mask_path (Path): Path to the tissue mask.
        - atlas_mask_path (Path): Path to the atlas mask.

    Returns:
        - mask_img (np.ndarray): the combined mask image.
    """
    mask_img = None

    # Load and warp the tissue mask to atlas space (if provided)
    if tissue_mask_path is not None:
        if not Path(tissue_mask_path).exists():
            raise FileNotFoundError(f"Tissue mask not found: {tissue_mask_path}")
        tissue_mask_img = tissue_mask_to_atlas_space(sample_path, tissue_mask_path, fixed_reg_input, atlas_path, pad_percent=pad_percent, verbose=verbose)
        mask_img = tissue_mask_img

    # Load the atlas mask (if provided)
    if atlas_mask_path is not None:
        if not Path(atlas_mask_path).exists():
            raise FileNotFoundError(f"Atlas mask not found: {atlas_mask_path}")
        atlas_mask_img = load_3D_img(atlas_mask_path, verbose=verbose)
        atlas_mask_img = np.where(atlas_mask_img > 0, 1, 0).astype(np.uint8)

        if mask_img is None:
            mask_img = atlas_mask_img
        else:
            # Combine tissue and atlas masks by applying both
            mask_img = mask_img * atlas_mask_img  # Intersection of both masks

    # If no mask was provided, initialize the mask to include all voxels
    if mask_img is None:
        nii = nib.load(input_path)
        img = np.asanyarray(nii.dataobj, dtype=np.float32).squeeze()
        mask_img = np.ones_like(img)  # No mask applied, use all voxels

    return mask_img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.tissue_mask is None and args.atlas_mask is None:
        print("\n    Warning: No mask provided. Z-scoring will be done for the whole image.\n")
        
    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)
    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:
            input_paths = list(sample_path.glob(str(args.input)))
            if not input_paths:
                print(f"\n    [red1]No files match the pattern {args.input} in {sample_path}\n")
                continue

            for input_path in input_paths:
                if args.tissue_mask is not None:
                    tissue_mask_path = sample_path / args.tissue_mask   
                else:
                    tissue_mask_path = None

                if args.atlas_mask is not None:
                    atlas_mask_path = sample_path / args.atlas_mask
                else:
                    atlas_mask_path = None

                # Get the mask image
                pad_percent = get_pad_percent(sample_path, args.pad_percent)
                mask_img = z_score_mask(sample_path, input_path, args.fixed_reg_in, args.atlas, tissue_mask_path, atlas_mask_path, pad_percent=pad_percent, verbose=args.verbose)

                # Z-score the image using the mask and save the output
                z_score(input_path, mask_img, args.suffix)
            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()