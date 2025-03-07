#!/usr/bin/env python3

"""
Use ``vstats_z_score_cwd`` (``zsc``) from UNRAVEL to z-score .nii.gz images in the current directory.

Prereqs:
    - ``vstats_prep``

Outputs:
    - <path/input_img>_z.nii.gz (float32) saved in the same directory as the input image. 

Note:
    - z-score = (img.nii.gz - mean pixel intensity in brain)/standard deviation of intensity in brain
    - Voxels outside the mask are set to zero.

Next commands for voxel-wise stats: 
    - Aggregate atlas space IF images with ``utils_agg_files``.
    - If analyzing whole brains, consider using ``vstats_whole_to_avg`` to average left and right hemispheres.
    - If using side-specific z-scoring, use ``vstats_hemi_to_avg`` to average the images.
    - Prepend condition names with ``utils_prepend``.
    - Check images in FSLeyes (e.g., with ``vstats_check_fsleyes``) and run ``vstats`` to perform voxel-wise stats.

Usage:
------
    vstats_z_score_cwd -i '*.nii.gz' [-mas path/mask1.nii.gz path/mask2.nii.gz] [-s z] [-v]
"""

import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.img_io import load_nii
from unravel.voxel_stats.apply_mask import load_mask
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='Path to the image or images to z-score. Default: "*.nii.gz"', default='*.nii.gz', action=SM)
    opts.add_argument('-s', '--suffix', help='Output suffix. Default: z (.nii.gz replaced w/ _z.nii.gz)', default='z', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Set voxels outside the mask(s) to zero

@print_func_name_args_times()
def z_score_img(img, mask_img):
    """Z-score an ndarray using a mask.
    
    Parameters:
        - img (np.ndarray): the ndarray to be z-scored.
        - mask_img (np.ndarray): the brain mask ndarray
        
    Returns:
        - img_z (np.ndarray): the z-scored ndarray"""

    # Extract only the masked (nonzero) voxels
    masked_voxels = img[mask_img != 0]

    # Prevent division by zero
    if masked_voxels.size == 0:
        raise ValueError("Mask is empty or does not cover any nonzero values in the image.")

    mean_intensity = masked_voxels.mean()
    std_dev = masked_voxels.std()

    if std_dev == 0:
        raise ValueError("Standard deviation is zero. All masked voxels have the same intensity.")

    # Z-score the entire image (including unmasked areas)
    z_scored_img = (img - mean_intensity) / std_dev

    # Zero out voxels outside the mask
    z_scored_img[mask_img == 0] = 0

    return z_scored_img

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if Path(args.input).is_absolute():
        nii_paths = list(Path(args.input))
    else:
        nii_paths = list(Path.cwd().glob(args.input))

    # Load the first image to get the shape
    input_nii_path = nii_paths[0]
    img = load_nii(input_nii_path)

    # Load the mask(s) and combine them
    mask_imgs = [load_mask(path) for path in args.masks] if args.masks else []
    mask_img = np.ones(img.shape, dtype=bool) if not mask_imgs else np.logical_and.reduce(mask_imgs)

    # Z-score the image using the mask and save the output
    for nii_path in nii_paths:
        nii = nib.load(nii_path)
        img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
        z_scored_img = z_score_img(img, mask_img)

        # Save the z-scored image
        output_path = Path(str(input_nii_path).replace('.nii.gz', f'_{args.suffix}.nii.gz'))

        z_scored_nii = nib.Nifti1Image(z_scored_img, nii.affine, nii.header)
        z_scored_nii.header.set_data_dtype(np.float32)
        nib.save(z_scored_nii, output_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()