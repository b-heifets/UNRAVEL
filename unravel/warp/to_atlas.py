#!/usr/bin/env python3

"""
Use ``warp_to_atlas`` (``w2a``) from UNRAVEL to warp a native image to atlas space.

Prereqs: 
    ``reg``

Input examples (path is relative to ./sample??; 1st glob match processed): 
    `*`.czi, cfos/`*`.tif, cfos, `*`.tif, `*`.h5, or `*`.zarr 

Usage:
------
    warp_to_atlas -i cfos -o img_in_atlas_space.nii.gz [--channel 1] [-md path/metadata.txt] [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-dt uint16] [-fri reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz] [--reg_res 50] [-inp bSpline] [-zo 1] [-mi] [-d list of paths] [-p sample??] [-v]
"""

import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.image_io.io_nii import convert_dtype
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt
from unravel.core.img_tools import pad
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.register.reg_prep import reg_prep
from unravel.warp.warp import warp


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='INPUT: Path of native image relative to ./sample??', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='Output filename. E.g., img_in_atlas_space.nii.gz. Saved in ./sample??/atlas_space/', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--channel', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    opts.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-a', '--atlas', help='path/atlas.nii.gz for use as the fixed image (Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)
    opts.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Percentage of padding that was added to each dimension of the fixed image during ``reg``. Default: 0.15 (15%%).', default=0.15, type=float, action=SM)
    opts.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default], multiLabel, nearestNeighbor).', default='bSpline', action=SM) # or 
    opts.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the raw image to --reg_res. Default: 1', default=1, type=int, action=SM)

    compatability = parser.add_argument_group('Compatability options')
    compatability.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

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
def to_atlas(sample_path, img, fixed_reg_in, atlas, output, interpol, dtype='uint16', pad_percent=0.15):
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
    img = pad(img, pad_percent=pad_percent)

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

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            output = sample_path / "atlas_space" / args.output
            output.parent.mkdir(exist_ok=True, parents=True)
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                continue

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()

            # Load full res image [and xy and z voxel size in microns], to be resampled [and reoriented], padded, and warped
            img_path = sample_path / args.input
            img = load_3D_img(img_path, args.channel, verbose=args.verbose)

            # Resample the rb_img to the resolution of registration (and optionally reorient for compatibility with MIRACL)
            img = reg_prep(img, xy_res, z_res, args.reg_res, args.zoom_order, args.miracl)

            # Warp native image to atlas space
            to_atlas(sample_path, img, args.fixed_reg_in, args.atlas, output, args.interpol, dtype='uint16', pad_percent=args.pad_percent)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()