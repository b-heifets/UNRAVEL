#!/usr/bin/env python3

"""
Use ``reg`` from UNRAVEL to register an average template brain/atlas to a resampled autofl brain. 

Usage for tissue registration:
------------------------------
    reg -m <path/template.nii.gz> -bc -sm 0.4 -ort <3 letter orientation code>

Usage for atlas to atlas registration:
--------------------------------------
    reg -m <path/atlas1.nii.gz> -f <path/atlas2.nii.gz> -m2 <path/atlas2.nii.gz>

Usage for template to template registration:
--------------------------------------------
    reg -m <path/template1.nii.gz> -f <path/template2.nii.gz> -m2 <path/template2.nii.gz> -inp linear

ort_code letter options: 
    - A/P=Anterior/Posterior
    - L/R=Left/Right
    - S/I=Superior/Interior
    - The side of the brain at the positive direction of the x, y, and z axes determines the 3 letters (axis order xyz)

Prereqs: 
    ``reg_prep``, [``seg_copy_tifs``], & [``seg_brain_mask``]

Next steps: 
    ``reg_check`` and ``vstats_prep``

Note:
    - Images in reg_inputs are not padded.
    - Images in reg_outputs have 15% padding.
"""

import argparse
import os
import subprocess
import ants
import nibabel as nib
from ants import n4_bias_field_correction, registration
from pathlib import Path
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import gaussian_filter

from unravel.image_io.reorient_nii import reorient_nii
from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_io import resolve_path
from unravel.core.img_tools import pad
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.warp.warp import warp


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments: 
    parser.add_argument('-m', '--moving_img', help='path/moving_img.nii.gz (e.g., average template optimally matching tissue)', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-f', '--fixed_img', help='reg_inputs/autofl_50um_masked.nii.gz (from ``reg_prep``)', default="reg_inputs/autofl_50um_masked.nii.gz", action=SM)
    parser.add_argument('-mas', '--mask', help="Brain mask for bias correction. Default: reg_inputs/autofl_50um_brain_mask.nii.gz. or pass in None", default="reg_inputs/autofl_50um_brain_mask.nii.gz", action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from ``reg`` (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-bc', '--bias_correct', help='Perform N4 bias field correction. Default: False', action='store_true', default=False)
    parser.add_argument('-sm', '--smooth', help='Sigma value for smoothing the fixed image. Default: 0 for no smoothing. Use 0.4 for autofl', default=0, type=float, action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code of fixed image if not set in fixed_img (e.g., RAS)', action=SM)
    parser.add_argument('-m2', '--moving_img2', help='path/atlas.nii.gz (outputs <reg_outputs>/<atlas>_in_tissue_space.nii.gz for checking reg; Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-inp', '--interpol', help='Interpolation method for warping -m2 to padded fixed img space (nearestNeighbor, multiLabel [default], linear, bSpline)', default="multiLabel", action=SM)
    parser.add_argument('-it', '--init_time', help='Time in seconds allowed for ``reg_affine_initializer`` to run. Default: 30' , default='30', type=str, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def bias_correction(image_path, mask_path=None, shrink_factor=2, verbose=False):
    """Perform N4 bias field correction on a .nii.gz and return an ndarray

    Args:
        image_path (str): Path to input image.nii.gz
        mask_path (str): Path to mask image.nii.gz
        shrink_factor (int): Shrink factor for bias field correction
        verbose (bool): Print output
        output_dir (str): Path to save corrected image"""
    ants_img = ants.image_read(str(image_path))
    if mask_path:
        ants_mask = ants.image_read(str(mask_path))
        ants_img_corrected = n4_bias_field_correction(image=ants_img, mask=ants_mask, shrink_factor=shrink_factor, verbose=verbose)
    else:
        ants_img_corrected = n4_bias_field_correction(ants_img)
    ndarray = ants_img_corrected.numpy()

    return ndarray


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Directory with outputs (e.g., transforms) from registration
            reg_outputs_path = resolve_path(sample_path, args.reg_outputs)
            reg_outputs_path.mkdir(parents=True, exist_ok=True)
 
            # Define inputs and outputs for the fixed image
            fixed_img_nii_path = resolve_path(sample_path, args.fixed_img)
            if not fixed_img_nii_path.exists():
                print(f"\n    [red]The fixed image to be padded for registration ({fixed_img_nii_path}) does not exist. Exiting.\n")
                import sys ; sys.exit()
            fixed_img_for_reg = str(Path(args.fixed_img).name).replace(".nii.gz", "_fixed_reg_input.nii.gz")
            fixed_img_for_reg_path = str(Path(reg_outputs_path, fixed_img_for_reg))

            # Preprocess the fixed image 
            if not Path(fixed_img_for_reg_path).exists():
                fixed_img_nii = nib.load(fixed_img_nii_path)

                # Optionally perform bias correction on the fixed image (e.g., when it is an autofluorescence image)
                if args.bias_correct: 
                    print(f'\n    Bias correcting the registration input\n')
                    if args.mask != "None": 
                        mask_path = resolve_path(sample_path, args.mask)
                        fixed_img = bias_correction(str(fixed_img_nii_path), mask_path=str(mask_path), shrink_factor=2, verbose=args.verbose)
                    elif args.mask == "None": 
                        fixed_img = bias_correction(str(fixed_img_nii_path), mask_path=None, shrink_factor=2, verbose=args.verbose)
                else:
                    fixed_img = fixed_img_nii.get_fdata(dtype=np.float32)

                # Pad the fixed image with 15% of voxels on all sides (keeps moving img in frame during initial alignment and avoids edge effects)
                print(f'\n    Adding padding to the registration input\n')
                fixed_img = pad(fixed_img, pad_width=0.15)

                # Optionally smooth the fixed image (e.g., when it is an autofluorescence image)
                if args.smooth > 0:
                    print(f'\n    Smoothing the registration input\n')
                    fixed_img = gaussian_filter(fixed_img, sigma=args.smooth)

                # Create NIfTI, set header info, and save the registration input (reference image) 
                print(f'\n    Setting header info for the registration input\n')
                fixed_img = fixed_img.astype(np.float32) # Convert the fixed image to FLOAT32 for ANTsPy
                reg_inputs_fixed_img_nii = nib.Nifti1Image(fixed_img, fixed_img_nii.affine.copy(), fixed_img_nii.header)
                reg_inputs_fixed_img_nii.set_data_dtype(np.float32)

                # Set the orientation of the image (use if not already set correctly in the header; check with ``io_nii_info``)
                if args.ort_code: 
                    reg_inputs_fixed_img_nii = reorient_nii(reg_inputs_fixed_img_nii, args.ort_code, zero_origin=True, apply=False, form_code=1)

                # Save the fixed input for registration
                nib.save(reg_inputs_fixed_img_nii, fixed_img_for_reg_path)

            # Generate the initial transform matrix for aligning the moving image to the fixed image
            if not Path(reg_outputs_path, f"ANTsPy_init_tform.mat").exists():

                # Check if required files exist
                if not Path(fixed_img_for_reg_path).exists(): 
                    print(f"\n    [red]The fixed image for registration ({fixed_img_for_reg_path})does not exist. Exiting.\n")
                    import sys ; sys.exit()
                if not Path(args.moving_img).exists(): 
                    print(f"\n    [red]The moving image for registration ({args.moving_img}) does not exist. Exiting.\n")
                    import sys ; sys.exit()

                print(f'\n\n    Generating the initial transform matrix for aligning the moving image (e.g., template) to the fixed image (e.g., tissue) \n')
                command = [
                    'reg_affine_initializer', 
                    '-f', fixed_img_for_reg_path, 
                    '-m', args.moving_img, 
                    '-o', str(Path(reg_outputs_path, f"ANTsPy_init_tform.mat")), 
                    '-t', args.init_time # Time in seconds allowed for this step. Increase time out duration if needed.
                ]

                # Redirect stderr to os.devnull
                with open(os.devnull, 'w') as devnull:
                    subprocess.run(command, stderr=devnull)

            # Perform initial approximate alignment of the moving image to the fixed image
            init_align_out = str(Path(reg_outputs_path, str(Path(args.moving_img).name).replace(".nii.gz", "__initial_alignment_to_fixed_img.nii.gz")))
            if not Path(init_align_out).exists():
                print(f'\n    Applying the initial transform matrix to aligning the moving image to the fixed image \n')
                fixed_image = ants.image_read(fixed_img_for_reg_path)
                moving_image = ants.image_read(args.moving_img)
                transformed_image = ants.apply_transforms(
                    fixed=fixed_image,
                    moving=moving_image,
                    transformlist=[str(Path(reg_outputs_path, f"ANTsPy_init_tform.mat"))]
                )
                ants.image_write(transformed_image, str(Path(reg_outputs_path, init_align_out)))

            # Define final output and skip processing if it exists
            output = str(Path(reg_outputs_path, str(Path(args.moving_img).name).replace(".nii.gz", "__warped_to_fixed_image.nii.gz")))
            if not Path(output).exists():

                # Perform registration (reg is a dict with multiple outputs)
                print(f'\n    Running registration \n')
                output_prefix = str(Path(reg_outputs_path, "ANTsPy_"))
                reg = ants.registration(
                    fixed=fixed_image,  # e.g., fixed autofluo image
                    moving=transformed_image,  # e.g., the initially aligned moving image (e.g., template)
                    type_of_transform='SyN',  # SyN = symmetric normalization
                    grad_step=0.1,  # Gradient step size
                    syn_metric='CC',  # Cross-correlation
                    syn_sampling=2,  # Corresponds to CC radius
                    reg_iterations=(100, 70, 50, 20),  # Convergence criteria
                    outprefix=output_prefix, 
                    verbose=args.verbose
                )

                # Save the warped moving image output
                ants.image_write(reg['warpedmovout'], output)  # The interpolation method is not NN or multiLabel
                print(f"\nTransformed moving image saved to: \n{output}")

                # Save the warped fixed image output (optional)
                # warpedfixout = str(Path(reg_outputs_path, str(Path(args.fixed_img).name).replace(".nii.gz", "__warped_to_moving_image.nii.gz")))
                # ants.image_write(reg['warpedfixout'], warpedfixout)
                # print(f"\nTransformed fixed image saved to: \n{warpedfixout}")

            # Warp the atlas image to the tissue image for checking reg (naming prioritizes the common usage)
            warped_atlas = str(Path(reg_outputs_path, str(Path(args.moving_img2).name).replace(".nii.gz", "_in_tissue_space.nii.gz")))
            if not Path(warped_atlas).exists():
                print(f'\n    Warping the atlas to padded fixed image space for checking reg: reg_outputs/<atlas>_in_tissue_space.nii.gz\n')
                warp(reg_outputs_path, args.moving_img2, fixed_img_for_reg_path, warped_atlas, inverse=False, interpol=args.interpol)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()