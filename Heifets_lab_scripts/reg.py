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


def parse_args():
    parser = argparse.ArgumentParser(description='Registers average template brain/atlas to downsampled autofl brain. Check accuracy w/ ./reg_final outputs in itksnap or fsleyes', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments: 
    parser.add_argument('-f', '--fixed_img', help='path/prep_reg_output_image.nii.gz (typically 50 um resolution)', required=True, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/moving_img.nii.gz (e.g., average template)', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-o', '--output', help='Warped moving image aligned with the fixed image. Default: <moving_img>__warped_moving_img.nii.gz', default=None, action=SM)
    parser.add_argument('-mas', '--mask', help="<brain_mask>.nii.gz", default=None, action=SM)
    parser.add_argument('-t', '--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-tp', '--tform_prefix', help='Prefix of the transforms output from ants.registration. Default: None', default="ANTsPy_", action=SM)
    parser.add_argument('-bc', '--bias_correct', help='Perform N4 bias field correction. Default: False', action='store_true', default=False)
    parser.add_argument('-pad', '--pad_img', help='If True, add 15 percent padding to image. Default: False', action='store_true', default=False)
    parser.add_argument('-sm', '--smooth', help='Sigma value for smoothing the fixed image. Default: 0 for no smoothing. Use 0.4 for autofl', default=0, type=float, action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code of fixed image if not set in fixed_img (e.g., RAS)', action=SM)
    parser.add_argument('-ia', '--init_align', help='Name of initially aligned image (moving reg input). Default: <moving_img>__initial_alignment_to_fixed_img.nii.gz' , default=None, action=SM)
    parser.add_argument('-it', '--init_time', help='Time in seconds allowed for ANTsPy_affine_initializer.py to run. Default: 30' , default='30', type=str, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: reg.py -f <50um_autofl_img_masked.nii.gz> -mas <brain_mask.nii.gz> -m <path/template.nii.gz> -bc -pad -sm 0.4 -ort PLI

Outputs saved in transforms folder. 

ort_code letter options: A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior
Use of ort_code sets the orientation and zeros the image origin, so don't use it if the orientation is already set correctly (see nii_orientation.py)

Prereqs: 
prep_reg.py [and brain_mask.py] for warping an average template to the autofluo tissue
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

            # Directory with transforms from registration
            transforms_path = resolve_path(sample_path, args.transforms)
            transforms_path.mkdir(parents=True, exist_ok=True)
 
            # Define final output and skip processing if it exists
            output = str(Path(transforms_path, str(Path(args.moving_img).name).replace(".nii.gz", "__warped_to_fixed_image.nii.gz")))
            if Path(output).exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                return
            
            # Load the fixed image
            fixed_img_nii = nib.load(args.fixed_img)

            # Optionally perform bias correction on the fixed image (e.g., when it is an autofluorescence image)
            if args.bias_correct: 
                print(f'\n    Bias correcting the registration input\n')
                fixed_img = bias_correction(args.fixed_img, mask_path=args.mask, shrink_factor=2, verbose=args.verbose, output_dir=transforms_path)
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
            reg_input_nii = nib.Nifti1Image(fixed_img, fixed_img_nii.affine.copy(), fixed_img_nii.header)
            reg_input_nii.set_data_dtype(np.float32)

            # Set the orientation of the image (use if not already set correctly in the header; check with nii_orientation.py)
            if args.ort_code: 
                reg_input_nii_affine = reorient_nii(reg_input_nii, args.ort_code, zero_origin=True, apply=False, form_code=1)
                reg_input_nii = nib.Nifti1Image(reg_input_nii.get_fdata(dtype=np.float32), reg_input_nii_affine, header=reg_input_nii.header)

            # Save the fixed input for registration
            fixed_img_for_reg = str(Path(args.fixed_img).name).replace(".nii.gz", "_fixed_reg_input.nii.gz")
            nib.save(reg_input_nii, Path(transforms_path, fixed_img_for_reg))

            # Perform initial approximate alignment of the moving image to the fixed image
            print(f'\n\n    Generating the initial transform matrix for aligning the moving image (e.g., template) to the fixed image (e.g., tissue) \n')
            script_path = Path(Path(os.path.abspath(__file__)).parent, 'ANTsPy_affine_initializer.py')
            command = [
                'python', 
                script_path, 
                '-f', str(Path(transforms_path, fixed_img_for_reg)), 
                '-m', args.moving_img, 
                '-o', str(Path(transforms_path, f"{args.tform_prefix}init_tform.mat")), 
                '-t', args.init_time # Time in seconds allowed for this step. Increase time out duration if needed.
            ]

            # Redirect stderr to os.devnull
            with open(os.devnull, 'w') as devnull:
                subprocess.run(command, stderr=devnull)

            # Load images
            print(f'\n    Applying the initial transform matrix to aligning the moving image to the fixed image \n')
            fixed_image = ants.image_read(str(Path(transforms_path, fixed_img_for_reg)))
            moving_image = ants.image_read(args.moving_img)

            # Apply transformation
            transformed_image = ants.apply_transforms(
                fixed=fixed_image,
                moving=moving_image,
                transformlist=[str(Path(transforms_path, f"{args.tform_prefix}init_tform.mat"))]
            )

            # Save the transformed image
            if args.init_align: 
                init_align_out = Path(transforms_path, args.init_align)
            else: 
                init_align_out = str(Path(transforms_path, str(Path(args.moving_img).name).replace(".nii.gz", "__initial_alignment_to_fixed_img.nii.gz")))
            ants.image_write(transformed_image, str(Path(transforms_path, init_align_out)))

            # Perform registration (reg is a dict with multiple outputs)
            print(f'\n    Running registration \n')
            output_prefix = str(Path(transforms_path, args.tform_prefix))
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

            # Save the warped image output
            ants.image_write(reg['warpedmovout'], output)
            print(f"\nTransformed moving image saved to: \n{output}")

            # Save the warped image output
            warpedfixout = str(Path(transforms_path, str(Path(args.fixed_img).name).replace(".nii.gz", "__warped_to_moving_img.nii.gz")))
            ants.image_write(reg['warpedfixout'], warpedfixout)
            print(f"Transformed fixed image saved to: \n{warpedfixout}\n")

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()