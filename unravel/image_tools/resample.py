#!/usr/bin/env python3

"""
Use ``img_resample`` (``resample``) from UNRAVEL to resample an image.nii.gz and save it.

Usage with reference image:
---------------------------
    img_resample -i image.nii.gz -ref reference_image.nii.gz [-zo 0] [-o image_resampled.nii.gz] [-v]

Usage for isotropic resampling:
-------------------------------
    img_resample -i image.nii.gz -tr 50 [-zo 0] [-o image_resampled.nii.gz] [-v]

Usage for anisotropic resampling:
---------------------------------
    img_resample -i image.nii.gz -tr 200 10 10 -o image_200x10x10.nii.gz [-zo 0] [-v]
"""

from pathlib import Path
import nibabel as nib
from rich.traceback import install
import numpy as np
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.img_tools import resample, resample_nii
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, get_stem

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Image file path(s) or pattern(s), e.g., path/input_image.nii.gz or *.nii.gz', required=True, nargs='*', action=SM)
    reqs.add_argument('-tr', '--target_res', help='Target resolution in microns for resampling (can be isotropic or anisotropic)', default=None, type=float, nargs='*', action=SM)
    reqs.add_argument('-td', '--target_dims', help='Target dimensions for resampling (can be isotropic or anisotropic)', default=None, type=int, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--save_as', help='Output format extension (nii.gz, .zarr, .tif, or .h5). Default: .nii.gz', default='.nii.gz', choices=['.nii.gz', '.tif', '.zarr', '.h5'], action=SM)
    opts.add_argument('-zo', '--zoom_order', help='SciPy zoom order. Default: 0 (nearest-neighbor). Use 1 for linear interpolation.', default=0, type=int, action=SM)
    opts.add_argument('-o', '--out_dir', help='Optional output directory. If not provided, saves alongside input', default=None, action=SM)
    opts.add_argument('-c', '--channel', help='.czi channel number. e.g., 0 for autofluorescence and 1 for immunofluorescence', default=None, type=int, action=SM)
    opts.add_argument('-x', '--xy_res', help='xy resolution in microns for .tif, .zarr, or .h5 files.', type=float, action=SM)
    opts.add_argument('-z', '--z_res', help='z resolution in microns for .tif, .zarr, or .h5 files.', type=float, action=SM)
    opts.add_argument('-d', '--dtype', help='Data type if saving as .nii.gz. Options: uint8, uint16, float32.', default=None, action=SM)
    opts.add_argument('-r', '--reference', help='Reference image for output .nii.gz metadata.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Add args for scaling by a factor for each dimension (e.g. to downsample). Test if .nii.gz logic can be consolidated with the other logic for resampling.
# TODO: -td and -r are only supported for .nii.gz files. Add support for .tif, .zarr, and .h5 files.

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    image_paths = match_files(args.input)
    
    for image_path in image_paths:

        stem = get_stem(image_path)
        filename = stem + '_resampled' + args.save_as

        if args.out_dir:
            Path(args.out_dir).mkdir(parents=True, exist_ok=True)
            out_path = Path(args.out_dir) / filename
        else:
            out_path = image_path.with_name(filename)

        if str(image_path).endswith('.nii.gz') and args.save_as == '.nii.gz':

            nii = nib.load(image_path)

            if args.reference is not None:
                ref_nii = nib.load(args.reference)
                target_res = ref_nii.header.get_zooms()[:3]
                target_dims = ref_nii.shape
                resampled_nii = resample_nii(nii, target_res=target_res, target_dims=target_dims, zoom_order=args.zoom_order)
            elif args.target_res is not None:
                target_res = [res / 1000 for res in args.target_res]  # Convert target resolution from microns to mm
                if len(target_res) == 1:
                    target_res = target_res * 3  # Use isotropic resolution if only one value is provided (* 3 will repeat the value for x, y, and z)
                resampled_nii = resample_nii(nii, target_res=target_res, target_dims=args.target_dims, zoom_order=args.zoom_order)
            elif args.target_dims is not None:
                resampled_nii = resample_nii(nii, target_res=None, target_dims=args.target_dims, zoom_order=args.zoom_order)
            else:
                raise ValueError("Either target resolution, target dimensions, or a reference image must be specified.")

            data_type = nii.header.get_data_dtype()
            resampled_nii.set_data_dtype(data_type)

            nib.save(resampled_nii, out_path)

        else:

            xy_res = args.xy_res if args.xy_res is not None else None
            z_res = args.z_res if args.z_res is not None else None
        
            if xy_res is None or z_res is None:
                img, xy_res, z_res = load_3D_img(image_path, args.channel, return_res=True, verbose=args.verbose)
            else:
                img = load_3D_img(image_path, args.channel, verbose=args.verbose)

            img_resampled = resample(img, xy_res=xy_res, z_res=z_res, target_res=args.target_res, zoom_order=args.zoom_order)

            target_res_xy = args.target_res[0] 
            target_res_z = args.target_res[2] if len(args.target_res) == 3 else args.target_res[0]

            save_3D_img(img_resampled, out_path, xy_res=target_res_xy, z_res=target_res_z, data_type=args.dtype, reference_img=args.reference)

    verbose_end_msg()

if __name__ == '__main__':
    main()
