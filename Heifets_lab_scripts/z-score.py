#!/usr/bin/env python3

import argparse
import shutil
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from to_atlas import to_atlas
from unravel_config import Configuration
from unravel_img_io import load_3D_img
from unravel_utils import get_samples, initialize_progress_bar, print_func_name_args_times, print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Z-score an image using a brain mask', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_dir name for gathering outputs from all samples (use -e w/ all paths)', default=None, action=SM)
    parser.add_argument('-i', '--input_suffix', help='Input file name w/o "sample??_" (added automatically). E.g., ochann_rb4_gubra_space.nii.gz', required=True, action=SM)
    parser.add_argument('-mas1', '--tissue_mask', help='rel_path/brain_mask.nii.gz. Default: reg_inputs/autofl_50um_brain_mask.nii.gz', default="reg_inputs/autofl_50um_brain_mask.nii.gz", action=SM)
    parser.add_argument('-mas2', '--optional_mask', help='path/optional_mask.nii.gz (in atlas space)', default=None, action=SM)
    parser.add_argument('-n', '--no-default-mask', help='Provide flad to avoid use of mas1', action='store_true')
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from reg.py. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (nearestNeighbor, multiLabel [default]).', default='multiLabel', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = """Usage:   z-score.py -i ochann_rb4_gubra_space.nii.gz -mas1 reg_inputs/autofl_50um_brain_mask.nii.gz -v

Input:  atlas_space/sample??_ochann_rb4_gubra_space.nii.gz    
Outputs:  atlas_space/sample??_ochann_rb4_gubra_space_z.nii.gz & atlas_space/autofl_50um_brain_mask.nii.gz

z-score = (img.nii.gz - mean pixel intensity in brain)/standard deviation of intensity in brain

Prereqs:
    - The input image is assumed to be in atlas space (e.g., sample??_ochann_rb4_gubra_space.nii.gz from prep_vxw_stats.py).
    - A tissue mask is warped to atlas space for z-scoring (e.g., reg_inputs/autofl_50um_brain_mask.nii.gz from prep_reg.py).

Optional:
    - A second mask (already in atlas space) may be provided to exclude additional voxels.
"""
    return parser.parse_args()


@print_func_name_args_times()
def z_score(img, mask):
    """Z-score the image using the mask.
    
    Args:
        - img (str): the ndarray to be z-scored.
        - mask (str): the brain mask ndarray"""

    # Zero out voxels outside the mask
    masked_data = img * mask

    # Calculate mean and standard deviation for masked data
    masked_nonzero = masked_data[masked_data != 0] # Exclude zero voxels and flatten the array (1D)
    mean_intensity = masked_nonzero.mean()
    std_dev = masked_nonzero.std() 

    # Z-score calculation
    z_scored_img = (masked_data - mean_intensity) / std_dev

    return z_scored_img


def main(): 

    if args.target_dir is not None:
        # Create the target directory for copying outputs for vxw_stats.py
        target_dir = Path(args.target_dir)
        target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            input_name = f"{sample_path.name}_{args.input_suffix}"
            input_path = sample_path / "atlas_space" / input_name

            output = str(input_path).replace('.nii.gz', '_z.nii.gz')
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                continue

            nii = nib.load(input_path)
            img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

            if not args.no_default_mask:
                # Warp tissue mask to atlas space
                brain_mask_in_tissue_space = load_3D_img(Path(sample_path, args.tissue_mask))
                mask_output = input_path.parent / Path(args.tissue_mask).name
                to_atlas(sample_path, brain_mask_in_tissue_space, args.fixed_reg_in, args.atlas, mask_output, args.interpol, dtype='float32')
                mask = load_3D_img(mask_output)
            else:
                # Initialize mask as all true if no default mask is used
                mask = np.ones(img.shape, dtype=bool)

            if args.optional_mask:
                optional_mask = load_3D_img(args.optional_mask)
                mask *= optional_mask

            z_scored_img = z_score(img, mask)
            z_scored_nii = nib.Nifti1Image(z_scored_img, nii.affine, nii.header)
            nib.save(z_scored_nii, output)

            if args.target_dir is not None:
                target_output = target_dir / output.name
                shutil.copy(output, target_output)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()