#!/usr/bin/env python3

import argparse
import os
import subprocess
import ants
import nibabel as nib
from ants import n4_bias_field_correction, registration
from nibabel.orientations import axcodes2ornt, ornt_transform, io_orientation, inv_ornt_aff
from pathlib import Path
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import gaussian_filter

from argparse_utils import SM, SuppressMetavar
from reorient_nii import reorient_nii
from unravel_config import Configuration
from unravel_img_io import resolve_path
from unravel_img_tools import pad_img
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples
from warp import warp


def parse_args():
    parser = argparse.ArgumentParser(description='Registers average template brain/atlas to downsampled autofl brain. Check accuracy w/ ./reg_final outputs in itksnap or fsleyes', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments: 
    parser.add_argument('-m', '--moving_img', help='path/moving_img.nii.gz (e.g., average template optimally matching tissue)', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-f', '--fixed_img', help='reg_inputs/autofl_50um_masked.nii.gz (from prep_reg.py)', default="reg_inputs/autofl_50um_masked.nii.gz", action=SM)
    parser.add_argument('-o', '--output', help='Warped moving image aligned with the fixed image. Default: <moving_img>__warped_moving_img.nii.gz', default=None, action=SM)
    parser.add_argument('-mas', '--mask', help="Brain mask for bias correction. Default: reg_inputs/autofl_50um_brain_mask.nii.gz. or pass in None", default="reg_inputs/autofl_50um_brain_mask.nii.gz", action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from reg.py (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-tp', '--tform_prefix', help='Prefix of transforms output from ants.registration. Default: ANTsPy_', default="ANTsPy_", action=SM)
    parser.add_argument('-bc', '--bias_correct', help='Perform N4 bias field correction. Default: False', action='store_true', default=False)
    parser.add_argument('-pad', '--pad_img', help='If True, add 15 percent padding to image. Default: False', action='store_true', default=False)
    parser.add_argument('-sm', '--smooth', help='Sigma value for smoothing the fixed image. Default: 0 for no smoothing. Use 0.4 for autofl', default=0, type=float, action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code of fixed image if not set in fixed_img (e.g., RAS)', action=SM)
    parser.add_argument('-ia', '--init_align', help='Name of initially aligned image (moving reg input). Default: <moving_img>__initial_alignment_to_fixed_img.nii.gz' , default=None, action=SM)
    parser.add_argument('-it', '--init_time', help='Time in seconds allowed for ANTsPy_affine_initializer.py to run. Default: 30' , default='30', type=str, action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: reg.py -m <path/template.nii.gz> -bc -pad -sm 0.4 -ort <3 letter orientation code>

ort_code letter options: A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior
The side of the brain at the positive direction of the x, y, and z axes determine the 3 letters (axis order xyz)

Prereqs: 
prep_reg.py, [prep_brain_mask.py], & [brain_mask.py] for warping an average template to the autofluo tissue
"""
    return parser.parse_args()

# TODO: Warp atlas to tisse for checking reg

@print_func_name_args_times()
def bias_correction(image_path, mask_path=None, shrink_factor=2, verbose=False, output_dir=None):
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

def set_nii_orientation(nii_img, target_axcodes, zero_origin=True, qform_code=1, sform_code=1):
    """Set the orientation the the .nii.gz image header
    
    Arguments: 
    nii_img: a NIfTI image object from nibabel
    target_axcodes: a tuple of axis codes like ('R', 'A', 'S') or ('L', 'P', 'S')
    """

    img = nii_img.get_fdata(dtype=np.float32) 

    # Determine the current orientation of the ndarray
    current_ornt = io_orientation(nii_img.affine)

    # Convert target axis codes to an orientation
    target_ornt = axcodes2ornt(target_axcodes)

    # Find the transformation needed
    transformation_ornt = ornt_transform(current_ornt, target_ornt)

    # Adjust the affine to match the new orientation
    new_affine = inv_ornt_aff(transformation_ornt, img.shape) @ nii_img.affine

    # Zero the origin:
    if zero_origin:
        for i in range(3):
            new_affine[i,3] = 0     
        
    # Make the .nii.gz image with the adjusted header.
    nii_img_oriented = nib.Nifti1Image(img, new_affine, nii_img.header)

    # Set the header information
    nii_img_oriented.header['xyzt_units'] = 10 # mm, s
    nii_img_oriented.header['qform_code'] = qform_code
    nii_img_oriented.header['sform_code'] = sform_code
    nii_img_oriented.header['regular'] = b'r'

    return nii_img_oriented


def main(): 

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
            fixed_img_for_reg = str(Path(args.fixed_img).name).replace(".nii.gz", "_fixed_reg_input.nii.gz")
            fixed_img_for_reg_path = str(Path(reg_outputs_path, fixed_img_for_reg))

            # Preprocess the fixed image 
            if not fixed_img_nii_path.exists():
                fixed_img_nii = nib.load(fixed_img_nii_path)

                # Optionally perform bias correction on the fixed image (e.g., when it is an autofluorescence image)
                if args.bias_correct: 
                    print(f'\n    Bias correcting the registration input\n')
                    mask_path = resolve_path(sample_path, args.mask)
                    fixed_img = bias_correction(str(fixed_img_nii_path), mask_path=str(mask_path), shrink_factor=2, verbose=args.verbose, output_dir=reg_outputs_path)
                else:
                    fixed_img = fixed_img_nii.get_fdata(dtype=np.float32)

                # Optionally pad the fixed image with 15% of voxels on all sides
                if args.pad_img: 
                    print(f'\n    Adding padding to the registration input\n')
                    fixed_img = pad_img(fixed_img, pad_width=0.15)

                # Optionally smooth the fixed image (e.g., when it is an autofluorescence image)
                if args.smooth > 0:
                    print(f'\n    Smoothing the registration input\n')
                    fixed_img = gaussian_filter(fixed_img, sigma=args.smooth)

                # Create NIfTI, set header info, and save the registration input (reference image) 
                print(f'\n    Setting header info for the registration input\n')
                fixed_img = fixed_img.astype(np.float32) # Convert the fixed image to FLOAT32 for ANTs
                reg_inputs_fixed_img_nii = nib.Nifti1Image(fixed_img, fixed_img_nii.affine.copy(), fixed_img_nii.header)
                reg_inputs_fixed_img_nii.set_data_dtype(np.float32)

                # Set the orientation of the image (use if not already set correctly in the header; check with nii_orientation.py)
                if args.ort_code: 
                    reg_inputs_fixed_img_nii = reorient_nii(reg_inputs_fixed_img_nii, args.ort_code, zero_origin=True, apply=False, form_code=1)

                # Save the fixed input for registration
                nib.save(reg_inputs_fixed_img_nii, fixed_img_for_reg_path)

            # Generate the initial transform matrix for aligning the moving image to the fixed image
            if not Path(reg_outputs_path, f"{args.tform_prefix}init_tform.mat").exists():
                print(f'\n\n    Generating the initial transform matrix for aligning the moving image (e.g., template) to the fixed image (e.g., tissue) \n')
                script_path = Path(Path(os.path.abspath(__file__)).parent, 'ANTsPy_affine_initializer.py')
                command = [
                    'python', 
                    script_path, 
                    '-f', fixed_img_for_reg_path, 
                    '-m', args.moving_img, 
                    '-o', str(Path(reg_outputs_path, f"{args.tform_prefix}init_tform.mat")), 
                    '-t', args.init_time # Time in seconds allowed for this step. Increase time out duration if needed.
                ]

                # Redirect stderr to os.devnull
                with open(os.devnull, 'w') as devnull:
                    subprocess.run(command, stderr=devnull)

            # Perform initial approximate alignment of the moving image to the fixed image
            if args.init_align: 
                init_align_out = str(Path(reg_outputs_path, args.init_align))
            else: 
                init_align_out = str(Path(reg_outputs_path, str(Path(args.moving_img).name).replace(".nii.gz", "__initial_alignment_to_fixed_img.nii.gz")))
            if not Path(init_align_out).exists():
                print(f'\n    Applying the initial transform matrix to aligning the moving image to the fixed image \n')
                fixed_image = ants.image_read(fixed_img_for_reg_path)
                moving_image = ants.image_read(args.moving_img)
                transformed_image = ants.apply_transforms(
                    fixed=fixed_image,
                    moving=moving_image,
                    transformlist=[str(Path(reg_outputs_path, f"{args.tform_prefix}init_tform.mat"))]
                )
                ants.image_write(transformed_image, str(Path(reg_outputs_path, init_align_out)))

            # Define final output and skip processing if it exists
            output = str(Path(reg_outputs_path, str(Path(args.moving_img).name).replace(".nii.gz", "__warped_to_fixed_image.nii.gz")))
            if not Path(output).exists():

                # Perform registration (reg is a dict with multiple outputs)
                print(f'\n    Running registration \n')
                output_prefix = str(Path(reg_outputs_path, args.tform_prefix))
                reg = ants.registration(
                    fixed=fixed_image, # e.g., fixed autofluo image
                    moving=transformed_image, # e.g., the initially aligned moving image (e.g., template)
                    type_of_transform='SyN',  # SyN = symmetric normalization
                    grad_step=0.1, # Gradient step size
                    syn_metric='CC',  # Cross-correlation
                    syn_sampling=2,  # Corresponds to CC radius
                    reg_iterations=(100, 70, 50, 20),  # Convergence criteria
                    outprefix=output_prefix, 
                    verbose=args.verbose
                )

                # Save the warped moving image output
                ants.image_write(reg['warpedmovout'], output)
                print(f"\nTransformed moving image saved to: \n{output}")

                # # Save the warped fixed image output
                # warpedfixout = str(Path(reg_outputs_path, str(Path(args.fixed_img).name).replace(".nii.gz", "__warped_to_moving_img.nii.gz")))
                # ants.image_write(reg['warpedfixout'], warpedfixout)
                # print(f"Transformed fixed image saved to: \n{warpedfixout}\n")

            # Warp the atlas image to the tissue image for checking registration
            warped_atlas = str(Path(reg_outputs_path, str(Path(args.atlas).name).replace(".nii.gz", "_in_tissue_space.nii.gz")))
            if not Path(warped_atlas).exists():
                print(f'\n    Warping the atlas image to the tissue image for checking registration \n')
                warp(reg_outputs_path, args.atlas, fixed_img_for_reg_path, warped_atlas, inverse=False, interpol='multiLabel')

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()