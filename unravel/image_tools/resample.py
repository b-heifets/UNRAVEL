#!/usr/bin/env python3

"""
Use ``img_resample`` (``resample``) from UNRAVEL to resample a 3D image and save it.

Note:
    - target_res, xy_res, and z_res should have the same units (e.g., microns).
    - If saving as .nii.gz without a reference, orientation defaults to RAS. Use ``io_reorient_nii`` to set orientation.

Supports:
    - Input formats: .nii.gz, .tif, .zarr, .h5, .czi
    - Output formats: .nii.gz, .tif, .zarr, .h5

Usage:
------
    img_resample -i image.nii.gz [-tr target_res | -td target_dims | -sc scale_factor | -r reference_image] [-s save_as] [-zo zoom_order] [-o output_dir] [-c czi_channel] [-x xy_res] [-z z_res] [-d dtype] [-v]
    

Usage for isotropic resampling:
-------------------------------
    img_resample -i image.nii.gz -tr 50

Usage for anisotropic resampling:
---------------------------------
    img_resample -i image.nii.gz -tr 200 10 10

Usage for resampling by scale factor:
-------------------------------------
    img_resample -i image.nii.gz -sc 0.5

Usage to resample using a reference image:
------------------------------------------
    img_resample -i image.nii.gz -r ref.nii.gz

"""

import nibabel as nib
import numpy as np
from pathlib import Path
from rich.traceback import install
from rich import print
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.img_tools import resample
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, get_stem

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Image file path(s) or pattern(s), e.g., path/input_image.nii.gz or *.nii.gz', required=True, nargs='*', action=SM)

    input_group = parser.add_argument_group('Optional arguments for input processing')
    input_group.add_argument('-c', '--channel', help='Channel number. Default: 0', default=0, type=int, action=SM)
    input_group.add_argument('-x', '--xy_res', help='xy resolution (e.g., in microns) for input .tif, .zarr, or .h5 files.', type=float, action=SM)
    input_group.add_argument('-z', '--z_res', help='z resolution (e.g., in microns) for input .tif, .zarr, or .h5 files.', type=float, action=SM)

    resample_group = parser.add_argument_group('Optional arguments for resampling (MUST PROVIDE: -tr, -td, -sc, or -r)')
    resample_group.add_argument('-tr', '--target_res', help='Target resolution (e.g., in microns) for resampling (can be isotropic or anisotropic)', default=None, type=float, nargs='*', action=SM)
    resample_group.add_argument('-td', '--target_dims', help='Target dimensions for resampling (x, y, z). E.g., 512 512 30', default=None, type=int, nargs='*', action=SM)
    resample_group.add_argument('-sc', '--scale', help='Scaling factor (e.g., 0.5 or 2 or 0.5 1 1)', default=None, nargs='+', type=float, action=SM)
    resample_group.add_argument('-r', '--reference', help='Use reference image to set resampling parameters and .nii.gz metadata.', default=None, action=SM)
    resample_group.add_argument('-zo', '--zoom_order', help='SciPy zoom order. Default: 0 (nearest-neighbor). Use 1 for linear interpolation.', default=0, type=int, action=SM)

    save_group = parser.add_argument_group('Optional arguments for saving')
    save_group.add_argument('-s', '--save_as', help='Output format extension (nii.gz, .zarr, .tif, or .h5). Default: .nii.gz', default='.nii.gz', choices=['.nii.gz', '.tif', '.zarr', '.h5'], action=SM)
    save_group.add_argument('-o', '--out_dir', help='Optional output directory. If not provided, saves alongside input', default=None, action=SM)
    save_group.add_argument('-d', '--dtype', help='Data type if saving as .nii.gz. Options: uint8, uint16, float32.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if not any([args.target_res, args.target_dims, args.scale, args.reference]):
        raise ValueError("You must specify one of --target_res, --target_dims, --scale, or --reference.")


    image_paths = match_files(args.input)

    # Reference logic
    scale = args.scale
    target_dims = args.target_dims
    target_res = args.target_res

    if target_dims and len(target_dims) != 3:
        raise ValueError("Target dimensions must have 3 values (x, y, z).")

    if args.reference:
        if str(args.reference).endswith('.nii.gz') or str(args.reference).endswith('.czi'):
            ref_img, target_res_xy, target_res_z = load_3D_img(args.reference, channel=args.channel, return_res=True, verbose=args.verbose)
        else:
            ref_img = load_3D_img(args.reference, channel=args.channel, verbose=args.verbose)
        target_dims = ref_img.shape   

        if ref_img.ndim != 3:
            raise ValueError(f"Reference image {args.reference} must be a 3D image. Got {ref_img.ndim}.")

    for image_path in image_paths:
        stem = get_stem(image_path)
        filename = stem + '_resampled' + args.save_as

        if args.out_dir:
            Path(args.out_dir).mkdir(parents=True, exist_ok=True)
            out_path = Path(args.out_dir) / filename
        else:
            out_path = image_path.with_name(filename)

        # Load image and resolution
        xy_res, z_res = args.xy_res, args.z_res
        if xy_res is None or z_res is None:
            img, xy_res, z_res = load_3D_img(image_path, args.channel, return_res=True, verbose=args.verbose)
        else:
            img = load_3D_img(image_path, args.channel, verbose=args.verbose)

        # Resample
        img_resampled = resample(
            img,
            xy_res=xy_res,
            z_res=z_res,
            target_res=target_res,
            target_dims=target_dims,
            scale=scale,
            zoom_order=args.zoom_order,
        )

        # Determine output resolution for saving
        if scale:
            zooms = np.atleast_1d(scale)
            if len(zooms) == 1:
                zooms = [zooms[0]] * 3
            target_res_xy = xy_res / zooms[0]
            target_res_z = z_res / zooms[2] if len(zooms) > 2 else z_res / zooms[0]
        elif target_dims and len(target_dims) == 3:
            target_res_xy = xy_res * (img.shape[0] / target_dims[0])
            target_res_z = z_res * (img.shape[2] / target_dims[2])
        elif target_res:
            target_res = np.atleast_1d(target_res)
            if len(target_res) == 1:
                target_res = [target_res[0]] * 3
            elif len(target_res) != 3:
                raise ValueError("target_res must be a float or list of 3 floats.")
            target_res_xy = target_res[0]
            target_res_z = target_res[2]

        # Calculate zoom factors
        zoom_xy = xy_res / target_res_xy
        zoom_z  = z_res / target_res_z

        if args.verbose:
            print(f"\n[bold]{image_path.name}[/bold]")
            print(f"    Original shape: {img.shape}")
            print(f"    xy res: {xy_res} µm, z res: {z_res} µm")
            print(f"    Zoom factors: xy={zoom_xy}, z={zoom_z}")
            print(f"    Resampled shape: {img_resampled.shape}")
            print(f"    Target xy res: {target_res_xy} µm, Target z res: {target_res_z} µm")
            print(f"    Zoom order: {args.zoom_order}")
            print(f"    Output path: {out_path}\n")

        if args.reference and str(args.save_as) == '.nii.gz':
            save_3D_img(img_resampled, out_path, xy_res=target_res_xy, z_res=target_res_z, data_type=args.dtype, reference_img=args.reference, verbose=args.verbose)
        else:
            save_3D_img(img_resampled, out_path, xy_res=target_res_xy, z_res=target_res_z, verbose=args.verbose)

    verbose_end_msg()

if __name__ == '__main__':
    main()
