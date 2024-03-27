#!/usr/bin/env python3

import argparse
import ants
import math
import nibabel as nib
import sys
import numpy as np

from ants import n4_bias_field_correction, registration, apply_transforms_to_image
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import zoom, gaussian_filter
from argparse_utils import SM, SuppressMetavar
from unravel_config import Configuration
from unravel_img_io import load_3D_img, resolve_path
from unravel_img_tools import pad_img, reorient_for_raw_to_nii_conv, resample
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples






def parse_args():
    parser = argparse.ArgumentParser(description='Registers average template brain/atlas to downsampled autofl brain. Check accuracy w/ ./reg_final outputs in itksnap or fsleyes', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='path/prep_reg_output_image.nii.gz', required=True, action=SM)
    parser.add_argument('-m', '--mask', help="<brain_mask>.nii.gz", default=None, action=SM)
    parser.add_argument('-o', '--output', help='Output path. Default: <input>_bias.nii.gz', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.add_argument('-bc', '--bias_correct', help='Perform N4 bias field correction', action='store_true', default=False)
    parser.add_argument('-sm', '--smooth', help='Smooth image with Gaussian filter. Default: 0.25. For no smoothing, set to 0', default=0.25, type=float, action=SM)
    parser.add_argument('-oc', '--ort_code', help='3 letter orientation code (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior; Default: ALI)', default='ALI', action=SM)
    parser.add_argument('-an', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", action=SM)
    parser.add_argument('-a', '--atlas', help='<path/atlas> to warp (default: gubra_ano_split_10um.nii.gz)', default="/usr/local/gubra/gubra_ano_split_25um.nii.gz", action=SM)
    parser.add_argument('-r', '--res', help="Resolution of atlas in microns (10, 25, or 50; Default: 25)", default=25, type=int, action=SM)
    parser.add_argument('-s', '--side', help="Side for hemisphere registration (w, l or r; Default: w)", default='w', action=SM)
    parser.add_argument('-t', '--template', help='Template (moving img; Default: path/gubra_template_25um.nii.gz)', default="/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz",  action=SM)
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns (Default: 50)', default=50, type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, action=SM)
    return parser.parse_args()

def bias_correction(image_path, mask_path=None, shrink_factor=2, verbose=False, output_dir=None):
    """Performs N4 bias field correction on image
    Args:
        image_path (str): Path to input image.nii.gz
        mask_path (str): Path to mask image.nii.gz
        shrink_factor (int): Shrink factor for bias field correction
        verbose (bool): Print output
        output_dir (str): Path to save corrected image"""
    image = ants.image_read(str(image_path))
    if mask_path:
        mask = ants.image_read(str(mask_path))
        corrected_image = n4_bias_field_correction(image=str(image_path), mask=mask, shrink_factor=shrink_factor, verbose=verbose)
    else:
        corrected_image = n4_bias_field_correction(image)
    corrected_image_name = str(Path(image_path).name).replace('.nii.gz', '_bias.nii.gz')
    corrected_path = Path(output_dir) / corrected_image_name if output_dir else Path(image_path).parent / corrected_image_name
    ants.image_write(corrected_image, str(corrected_path))
    return corrected_path

def pad_image(image_path, pad_width=0.15):
    """Pads image by 15% of voxels on all sides"""
    image_data = load_nifti_image(image_path)
    pad_width = int(pad_width * image_data.shape[0])
    padded_img = np.pad(image_data, [(pad_width, pad_width)] * 3, mode='constant')
    return padded_img

def smooth_image(ndarray, sigma=None, res=50, kernel_size_in_vx=0.25):
    """Smooth ndarray with a Gaussian filter and return the smoothed image
    Args:
        ndarray (np.ndarray): Image data
        sigma (float): Standard deviation for Gaussian kernel
        res (int): Resolution of the image in microns
        kernel_size_in_vx (float): Kernel size in voxels"""
    if sigma is None:
        FWHM = kernel_size_in_vx * res  # 0.25 times the voxel size
        sigma = FWHM / (2 * math.sqrt(2 * math.log(2))) # Calculate sigma that corresponds to the FWHM
        sigma = sigma / res # Convert sigma from microns to voxel units
    smoothed_img = gaussian_filter(ndarray, sigma=sigma)
    return smoothed_img


def main(): 

    if len(args.ort_code) != 3 or not all(x in 'APRLIS' for x in args.ort_code):
        raise ValueError("Invalid 3 letter orientation code. Must be a combination of A/P, L/R, and S/I")
       

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            output = resolve_path(sample_path, args.output)
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                return
            
            # Directory with transforms from registration
            transforms_path = resolve_path(sample_path, args.transforms)

            # Bias correction
            if args.bias_correct: 
                corrected_path = bias_correction(args.input, mask_path=args.mask, shrink_factor=2, verbose=False, output_dir=transforms_path)
                img = load_3D_img(corrected_path, "xyz")
            else:
                img = load_3D_img(args.input, "xyz")

            # Pad with 15% of voxels on all sides
            img = pad_image(img, pad_width=0.15)

            # Smoothing
            if args.smooth > 0:
                img = smooth_image(img, sigma=None, res=args.reg_res, kernel_size_in_vx=args.smooth)

            ants.image_write(img, '/SSD3/mdma_v_meth/s16_reg_test/sample16/clar_allen_reg/clar_res0.05_sm_py.nii.gz')

            import sys ; sys.exit()

            ### Need to set orientation of the image


            # Define the paths to your fixed and moving images, and where to save the transformation matrix
            fixed_image_path = '/SSD3/mdma_v_meth/s16_reg_test/sample16/clar_allen_reg/clar_res0.05_sm_py.nii.gz'
            moving_image_path = '/usr/local/unravel/atlases/gubra/custom_templates/gubra_template_25um_OB_trim.nii.gz'
            output_transform_path = '/SSD3/mdma_v_meth/s16_reg_test/sample16/clar_allen_reg/init_tform_py.mat'

            # Load the fixed and moving images
            fixed_image = ants.image_read(fixed_image_path)
            moving_image = ants.image_read(moving_image_path)

            # Execute the affine initializer with the specified parameters
            txfn = ants.affine_initializer(
                fixed_image=fixed_image,
                moving_image=moving_image,
                search_factor=1,  # Degree of increments on the sphere to search
                radian_fraction=1,  # Defines the arc to search over
                use_principal_axis=False,  # Determines whether to initialize by principal axis
                local_search_iterations=500,  # Number of iterations for local optimization at each search point
                txfn=output_transform_path  # Path to save the transformation matrix
            )

            print(f"Transformation file saved to: {txfn}")


            # For example, with ANTsPy
            fixed_image = nib.load("resampled_image.nii.gz")
            moving_image = nib.load(args.template)
            
            reg_output = registration(fixed_image, moving_image)
            warped_moving_image = apply_transforms_to_image(fixed_image, moving_image, transform=reg_output['fwdtransforms'])
            save_nifti_image(warped_moving_image.numpy(), args.input, "warped_moving_image.nii.gz")

            # More operations...
            # ...

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()