#!/usr/bin/env python3

"""
Use ``warp_to_atlas`` from UNRAVEL to warp a native image to atlas space.

Usage:
------
    warp_to_atlas -i ochann -o img_in_atlas_space.nii.gz -x 3.5232 -z 6 [-mi -v] 

Prereqs: 
    ``reg``

Input examples (path is relative to ./sample??; 1st glob match processed): 
    <asterisk>.czi, ochann/<asterisk>.tif, ochann, <asterisk>.tif, <asterisk>.h5, or <asterisk>.zarr 
"""

import argparse
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.image_io.io_nii import convert_dtype
from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.img_tools import pad
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.register.reg_prep import reg_prep
from unravel.warp.warp import warp


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='INPUT: Path of native image relative to ./sample??', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Output img.nii.gz (saved as ./sample??/atlas_space/img.nii.gz', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz for use as the fixed image (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default]).', default='bSpline', action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the raw image. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def copy_nii_header(source_img, new_img):
    """Copy header info from nii_img to new_img"""
    fields_to_copy = [
        'xyzt_units', 'descrip', 'qform_code', 'sform_code',
        'qoffset_x', 'qoffset_y', 'qoffset_z', 'pixdim', 
    ]
    for field in fields_to_copy:
        new_img.header[field] = source_img.header[field]

    return new_img

@print_func_name_args_times()
def to_atlas(sample_path, img, fixed_reg_in, atlas, output, interpol, dtype='uint16'):
    """Warp the image to atlas space using ANTsPy.
    
    Args:
        - sample_path (Path): Path to the sample directory.
        - img (np.ndarray): 3D image.
        - fixed_reg_in (str): Name of the fixed image for registration.
        - atlas (str): Path to the atlas.
        - output (str): Path to the output.
        - interpol (str): Type of interpolation (linear, bSpline, nearestNeighbor, multiLabel).
        - dtype (str): Desired dtype for output (e.g., uint8, uint16). Default: uint16"""
    # Pad the image
    img = pad(img, pad_width=0.15)

    # Create NIfTI, set header info, and save the input for warp()
    fixed_reg_input = sample_path / fixed_reg_in
    reg_outputs_path = fixed_reg_input.parent
    warp_inputs_dir = reg_outputs_path / "warp_inputs"
    warp_inputs_dir.mkdir(exist_ok=True, parents=True)
    warp_input_path = str(warp_inputs_dir / output.name)
    print(f'\n    Setting header info and saving the input for warp() here: {warp_input_path}\n')
    img = img.astype(np.float32) # Convert the fixed image to FLOAT32 for ANTsPy
    fixed_reg_input_nii = nib.load(fixed_reg_input)
    img_nii = nib.Nifti1Image(img, fixed_reg_input_nii.affine.copy(), fixed_reg_input_nii.header)
    img_nii.set_data_dtype(np.float32) 
    nib.save(img_nii, warp_input_path)

    # Warp the image to atlas space
    print(f'\n    Warping image to atlas space\n')
    warp(reg_outputs_path, warp_input_path, atlas, output, inverse=True, interpol=interpol)

    # Optionally lower the dtype of the output if the desired dtype is not float32
    if dtype.lower() != 'float32':
        output_nii = nib.load(output)
        output_img = output_nii.get_fdata(dtype=np.float32)
        output_img = convert_dtype(output_img, dtype, scale_mode='none')
        output_nii = nib.Nifti1Image(output_img, output_nii.affine.copy(), output_nii.header)
        output_nii.header.set_data_dtype(dtype)
        nib.save(output_nii, output)


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

            output = sample_path / "atlas_space" / args.output
            output.parent.mkdir(exist_ok=True, parents=True)
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                continue

            # Load full res image [and xy and z voxel size in microns], to be resampled [and reoriented], padded, and warped
            img_path = sample_path / args.input
            img, xy_res, z_res = load_3D_img(img_path, args.chann_idx, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)

            # Resample the rb_img to the resolution of registration (and optionally reorient for compatibility with MIRACL)
            img = reg_prep(img, xy_res, z_res, args.reg_res, args.zoom_order, args.miracl)

            # Warp native image to atlas space
            to_atlas(sample_path, img, args.fixed_reg_in, args.atlas, output, args.interpol, dtype='uint16')

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()