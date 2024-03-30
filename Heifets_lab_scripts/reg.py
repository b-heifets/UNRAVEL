#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import ants
import shutil
import nibabel as nib
from ants import n4_bias_field_correction, registration
from nibabel.orientations import axcodes2ornt, ornt_transform, io_orientation, inv_ornt_aff
from pathlib import Path
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
    parser.add_argument('-f', '--fixed_input', help='path/prep_reg_output_image.nii.gz (typically 50 um resolution)', required=True, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/moving_img.nii.gz (e.g., average template)', required=True,  action=SM)

    # Optional arguments:
    parser.add_argument('-mas', '--mask', help="<brain_mask>.nii.gz", default=None, action=SM)
    parser.add_argument('-tf', '--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-op', '--output_prefix', help='Prefix of ants.registration outputs. Default: None', default=None, action=SM)
    parser.add_argument('-bc', '--bias_correct', help='Perform N4 bias field correction. Default: False', action='store_true', default=False)
    parser.add_argument('-pad', '--pad_img', help='If True, add 15 percent padding to image. Default: False', action='store_true', default=False)
    parser.add_argument('-sm', '--smooth', help='Sigma value for smoothing the fixed image. Default: 0 for no smoothing. Use 0.4 for autofl', default=0, type=float, action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code (e.g., PLI; A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior)', action=SM)
    parser.add_argument('-itx', '--init_tform', help='Name of the initial transformation matrix. Default: init_tform_py.mat', default="init_tform_py.mat", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: reg.py -f <50um_autofl_img_masked.nii.gz> -mas <brain_mask.nii.gz> -m <path/template.nii.gz> -bc -pad -sm 0.4 -ort PLI

Prereqs: 
prep_reg.py [and brain_mask.py] for warping an average template to the autofluo tissue
"""
    return parser.parse_args()


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

    img = nii_img.get_fdata() 

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

    if len(args.ort_code) != 3 or not all(x in 'APRLIS' for x in args.ort_code):
        raise ValueError("Invalid 3 letter orientation code. Must be a combination of A/P, L/R, and S/I")
       
    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Directory with transforms from registration
            transforms_path = resolve_path(sample_path, args.transforms)

            # Define outputs
            if not args.output_prefix:
                output_prefix = str(Path(transforms_path, ''))
            else:
                output_prefix = str(Path(transforms_path, args.output_prefix))
            output = f'{output_prefix}Warped.nii.gz'
            fixed_img_for_reg = str(Path(args.fixed_input).name).replace(".nii.gz", "_fixed_reg_input.nii.gz")
            if Path(output).exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                return
            
            # Bias correction
            if args.bias_correct: 
                print(f'\n    Bias correcting the registration input\n')
                img = bias_correction(args.fixed_input, mask_path=args.mask, shrink_factor=2, verbose=args.verbose, output_dir=transforms_path)
            else:
                nii_img = nib.load(args.fixed_input)
                img = nii_img.get_fdata()

            # Pad with 15% of voxels on all sides
            if args.pad_img: 
                print(f'\n    Adding padding to the registration input\n')
                img = pad_img(img, pad_width=0.15)

            # Smoothing
            if args.smooth > 0:
                print(f'\n    Smoothing the registration input\n')
                img = gaussian_filter(img, sigma=args.smooth)

            # Conver ndarray to FLOAT32 for ANTs
            img = img.astype('float32') 

            # Create NIfTI, set header info, and save the registration input (reference image) 
            print(f'\n    Setting header info for the registration input\n')
            input_nii = nib.load(args.fixed_input)
            reg_input_nii = nib.Nifti1Image(img, input_nii.affine.copy())

            # Set the orientation of the image
            reg_input_nii = reorient_nii(reg_input_nii, args.ort_code, zero_origin=True, code=1)
            nib.save(reg_input_nii, Path(transforms_path, fixed_img_for_reg))

            # Get the absolute path to the currently running script
            print(f'\n    Generating the initial transform matrix for aligning the moving image (e.g., template) to the fixed image (e.g., tissue) \n')
            script_path = Path(Path(os.path.abspath(__file__)).parent, 'ANTsPy_affine_initializer.py')
            command = [
                'python', 
                script_path, 
                '-f', str(Path(transforms_path, fixed_img_for_reg)), 
                '-m', args.moving_img, 
                '-o', str(Path(transforms_path, args.init_tform)), 
                '-t', '10'
            ]

            # Redirect stderr to os.devnull, leaving stdout unaffected
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
                transformlist=[str(Path(transforms_path, args.init_tform))]
            )

            # Save the transformed image
            ants.image_write(transformed_image, str(Path(transforms_path, 'initial_alignment_of_moving_image.nii.gz')))

            # Perform registration (reg is a dict with multiple outputs)
            reg = ants.registration(
                fixed=fixed_image, # e.g., reg_input.nii.gz
                moving=transformed_image, # e.g., the initially aligned template
                type_of_transform='SyN',  # SyN = symmetric normalization
                grad_step=0.1, # Gradient step size
                syn_metric='CC',  # Cross-correlation
                syn_sampling=2,  # Corresponds to CC radius
                reg_iterations=(100, 70, 50, 20),  # Convergence criteria
                outprefix=output_prefix, # Can be omitted to use a default prefix of "" 
                verbose=args.verbose
            )

            # Save the warped image output
            ants.image_write(reg['warpedmovout'], output)
            print(f"Transformed image saved to: {output}")

            # # Handle forward transformation fields
            # for i, transform_path in enumerate(reg['fwdtransforms']):
            #     # Determine the type of transformation from its filename and construct the new filename accordingly
            #     if transform_path.endswith('.mat'):
            #         new_filename = f"{output_prefix}{i}GenericAffine.mat"
            #     else:
            #         new_filename = f"{output_prefix}{i}Warp.nii.gz"
            #     shutil.copy(transform_path, new_filename)
            #     print(f"Forward transform saved to: {new_filename}")

            # # Handle inverse transformation fields, if they exist
            # for i, transform_path in enumerate(reg['invtransforms']):
            #     # The transformation type is inferred from the filename as above
            #     if transform_path.endswith('.mat'):
            #         new_filename = f"{output_prefix}{i}InverseGenericAffine.mat"
            #     else:
            #         new_filename = f"{output_prefix}{i}InverseWarp.nii.gz"
            #     shutil.copy(transform_path, new_filename)
            #     print(f"Inverse transform saved to: {new_filename}")

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()