#!/usr/bin/env python3

import argparse
import shutil
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from nii_io import convert_dtype
from prep_reg import prep_reg
from unravel_config import Configuration
from unravel_img_io import load_3D_img
from unravel_img_tools import pad_img, rolling_ball_subtraction_opencv_parallel
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples
from warp import warp


def parse_args():
    parser = argparse.ArgumentParser(description='Loads immunofluo image, subtracts background, and warps to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_dir name for gathering outputs from all samples (use -e w/ all paths)', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='path to full res image', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-l', '--label', help='Fluorescent label (e.g., cfos). Default: ochann)', default="ochann", action=SM)
    parser.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels (Default: 4)', default=4, type=int, action=SM)
    parser.add_argument('-an', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", action=SM)
    parser.add_argument('-o', '--output', help='Output file name (Default: <sample??>_<label>_rb<4>_<gubra>_space.nii.gz) or path rel to sample??', default=None, action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from reg.py. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the raw image. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-th', '--threads', help='Number of threads for rolling ball subtraction. Default: 8', default=8, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: prep_vxw_stats.py -i ochann -rb 4 -x 3.5232 -z 6 -v

Prereqs: 
reg.py

Input examples (path is relative to ./sample??; 1st glob match processed): 
*.czi, ochann/*.tif, ochann, *.tif, *.h5, or *.zarr

outputs: .[/sample??]/sample??_ochann_rb4_gubra_space.nii.gz or custom output path

next steps: Aggregate outputs and run vxw_stats.py"""
    return parser.parse_args()


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

            default_output_name = f"{sample_path.name}_{args.label}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz"
            output = sample_path / (args.output or default_output_name)

            if output.exists():
                print(f"\n    {output} already exists. Skipping.")
                continue
            
            # Load full res image [and xy and z voxel size in microns], to be resampled [and reoriented], padded, and warped
            img_path = sample_path / args.input
            img, xy_res, z_res = load_3D_img(img_path, args.chann_idx, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)

            # Rolling ball background subtraction
            rb_img = rolling_ball_subtraction_opencv_parallel(img, radius=args.rb_radius, threads=args.threads)  

            # Resample the rb_img to the resolution of registration (and optionally reorient for compatibility with MIRACL)
            rb_img = prep_reg(rb_img, xy_res, z_res, args.reg_res, args.zoom_order, args.miracl)

            # Pad the image
            rb_img = pad_img(rb_img, pad_width=0.15)

            # Create NIfTI, set header info, and save the registration input (reference image) 
            print(f'\n    Setting header info and saving temp .nii.gz for warping\n')
            rb_img = rb_img.astype(np.float32) # Convert the fixed image to FLOAT32 for ANTsPy
            fixed_reg_input = sample_path / args.fixed_reg_in
            fixed_reg_input_nii = nib.load(fixed_reg_input)
            rb_img_nii = nib.Nifti1Image(rb_img, fixed_reg_input_nii.affine.copy(), fixed_reg_input_nii.header)
            rb_img_nii.set_data_dtype(np.float32) 

            # Save the image for warping
            reg_outputs_path = fixed_reg_input.parent
            temp_output = str(reg_outputs_path / f"{sample_path.name}_{args.label}_rb{args.rb_radius}_{args.atlas_name}_space_before_warping.nii.gz")
            nib.save(rb_img_nii, temp_output)

            # Warp the image to atlas space
            print(f'\n    Warping preprocessed image to atlas space\n')
            warp(reg_outputs_path, temp_output, args.atlas, output, inverse=True, interpol='bSpline')

            # Optionally lower the dtype of the output if the desired dtype is not float32
            if args.dtype.lower() != 'float32':
                output_nii = nib.load(output)
                output_img = output_nii.get_fdata(dtype=np.float32)  # Ensures data is loaded in float32 for precision
                # output_img = output_img.astype(args.dtype)  # Convert dtype as specified
                output_img = convert_dtype(output_img, args.dtype, scale_mode='none')
                output_nii = nib.Nifti1Image(output_img, output_nii.affine.copy(), output_nii.header)
                output_nii.header.set_data_dtype(args.dtype)
                nib.save(output_nii, output)

            # Remove temp file
            Path(temp_output).unlink()

            if args.target_dir is not None:
                # Copy output to the target directory
                target_output = target_dir / output.name
                shutil.copy(output, target_output)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()