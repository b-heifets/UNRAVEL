#!/usr/bin/env python3

"""
Use ``vstats_z_score`` from UNRAVEL to z-score an atlas space image using a tissue mask and/or an atlas mask.

Usage w/ a tissue mask (warped to atlas space):
-----------------------------------------------
    vstats_z_score -i atlas_space/sample??_cfos_rb4_atlas_space.nii.gz -v

Usage w/ an atlas mask (warped to atlas space):
-----------------------------------------------
    vstats_z_score -i path/img.nii.gz -n -amas path/atlas_mask.nii.gz -v

Usage w/ both masks for side-specific z-scoring:
------------------------------------------------
    vstats_z_score -i atlas_space/sample??_cfos_rb4_atlas_space.nii.gz -amas path/RH_mask.nii.gz -s RHz -v

Next steps: 
    - Aggregate outputs with ``utils_agg_files``.
    - If analyzing whole brains, consider using ``vstats_whole_to_avg`` to average hemispheres together.
    - If using side-specific z-scoring, next use ``vstats_hemi_to_avg`` to average the images.
    - Run ``vstats`` to perform voxel-wise stats.

Outputs:
    - <path/input_img>_z.nii.gz (float32)
    - [sample??/atlas_space/autofl_50um_brain_mask.nii.gz]

z-score = (img.nii.gz - mean pixel intensity in brain)/standard deviation of intensity in brain

Prereqs:
    ``vstats_prep`` for inputs [& ``seg_brain_mask`` for tissue masks]
"""

import argparse
import shutil
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, initialize_progress_bar, print_func_name_args_times
from unravel.warp.to_atlas import to_atlas


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_dir name for gathering outputs from all samples (use -e w/ all paths)', default=None, action=SM)
    parser.add_argument('-i', '--input', help='full_path/img.nii.gz or rel_path/img.nii.gz ("sample??" works for batch processing)', required=True, action=SM)
    parser.add_argument('-s', '--suffix', help='Output suffix. Default: z (.nii.gz replaced w/ _z.nii.gz)', default='z', action=SM)
    parser.add_argument('-tmas', '--tissue_mask', help='rel_path/brain_mask.nii.gz. Default: reg_inputs/autofl_50um_brain_mask.nii.gz', default="reg_inputs/autofl_50um_brain_mask.nii.gz", action=SM)
    parser.add_argument('-amas', '--atlas_mask', help='path/atlas_mask.nii.gz (can use tmas and/or amas)', default=None, action=SM)
    parser.add_argument('-n', '--no_tmask', help='Provide flag to avoid use of tmas', action='store_true')
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz. It is used as a fixed image for warping a brain mask to atlas space (Default: path/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (nearestNeighbor, multiLabel [default]).', default='multiLabel', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Set voxels outside the mask(s) to zero


@print_func_name_args_times()
def z_score(img, mask):
    """Z-score the image using the mask.
    
    Args:
        - img (str): the ndarray to be z-scored.
        - mask (str): the brain mask ndarray"""

    # Zero out voxels outside the mask
    masked_data = img * mask

    # Calculate mean and standard deviation for masked data
    masked_nonzero = masked_data[masked_data != 0]  # Exclude zero voxels

    mean_intensity = masked_nonzero.mean()
    std_dev = masked_nonzero.std()

    # Z-score calculation
    z_scored_img = (masked_data - mean_intensity) / std_dev

    return z_scored_img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.no_tmask and args.atlas_mask is None: 
        print("\n    [red]Please provide a path for --atlas_mask if --tissue_mask is not used\n")

    if args.target_dir is not None:
        # Create the target directory for copying outputs for ``vstats``
        target_dir = Path(args.target_dir)
        target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            if Path(args.input).is_absolute():
                input_path = Path(args.input)
            else:
                if f"{args.pattern}" in args.input:
                    input_path = Path(sample_path / args.input.replace(f"{args.pattern}", f"{sample_path.name}"))
                else:
                    input_path = Path(sample_path / args.input)
            
            if not input_path.exists():
                print(f"\n [red]The specified input file {input_path} does not exist.")
                import sys ; sys.exit()

            output = Path(str(input_path).replace('.nii.gz', f'_{args.suffix}.nii.gz'))
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                continue

            nii = nib.load(input_path)
            img = np.asanyarray(nii.dataobj, dtype=np.float32).squeeze()

            if not args.no_tmask:
                # Warp tissue mask to atlas space
                brain_mask_in_tissue_space = load_3D_img(Path(sample_path, args.tissue_mask))
                mask_output = input_path.parent / Path(args.tissue_mask).name

                fixed_reg_input = Path(sample_path, args.fixed_reg_in)    
                if not fixed_reg_input.exists():
                    fixed_reg_input = sample_path / "reg_outputs" / "autofl_50um_fixed_reg_input.nii.gz"

                to_atlas(sample_path, brain_mask_in_tissue_space, fixed_reg_input, args.atlas, mask_output, args.interpol, dtype='float32')
                mask = load_3D_img(mask_output)
                mask = np.where(mask > 0, 1, 0).astype(np.uint8)

            if args.atlas_mask:
                atlas_mask_img = load_3D_img(args.atlas_mask)
                atlas_mask_img = np.where(atlas_mask_img > 0, 1, 0).astype(np.uint8)

            if args.no_tmask: 
                mask = atlas_mask_img
            elif args.atlas_mask: 
                mask *= atlas_mask_img

            z_scored_img = z_score(img, mask)
            nii.header.set_data_dtype(np.float32)
            z_scored_nii = nib.Nifti1Image(z_scored_img, nii.affine, nii.header)
            nib.save(z_scored_nii, output)

            if args.target_dir is not None:
                target_output = target_dir / output.name
                shutil.copy(output, target_output)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()