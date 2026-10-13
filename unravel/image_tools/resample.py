#!/usr/bin/env python3

"""
Use ``img_resample`` (``resample``) from UNRAVEL to resample a 3D image.

Notes:
    - Resolutions are in microns, in array-axis order (not world RAS order).
      For a PIR NIfTI, -tr 200 10 10 sets P/I/R spacing to 200/10/10 µm.
    - NIfTI orientation and the center of voxel (0, 0, 0) are preserved.
      Unknown NIfTI spatial units are assumed to be mm, as elsewhere in UNRAVEL.
    - Use --input_res for non-NIfTI inputs with unequal x/y spacing;
      otherwise their input metadata uses UNRAVEL's xy_res/z_res convention.
    - A NIfTI reference defines the complete output grid; it does not register
      images. Non-NIfTI images use a zero-origin RAS grid.
    - Output dimensions are rounded; voxel sizes stay at the requested values.
      Sampling outside the source uses zero. Order 0 is intended for labels.
    - TIFF output is a single OME-TIFF, with independent x/y/z voxel sizes.
      HDF5/Zarr outputs store data and spacing in z/y/x order.

Usage:
------
    resample -i annotation_10.nii.gz -tr 200 10 10 -zo 0 -d uint16 -n annotation_200x10x10.nii.gz
    resample -i image.nii.gz -tr 50
    resample -i image.nii.gz -td 512 512 30
    resample -i image.nii.gz -sc 0.5
    resample -i image.nii.gz -r reference.nii.gz
    resample -i image.tif -ir 2 3 5 -tr 10 10 20
"""

import nibabel as nib
import numpy as np
from pathlib import Path
from rich.traceback import install
from rich import print
from scipy.ndimage import affine_transform

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, get_stem


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument(
        '-i', '--input',
        help='Image file path(s) or pattern(s), e.g., path/input_image.nii.gz or *.nii.gz',
        required=True, nargs='*', action=SM
    )

    input_group = parser.add_argument_group('Optional arguments for input processing')
    input_group.add_argument('-ir', '--input_res', help='Input voxel sizes in microns: one value or three in array-axis order. Overrides metadata.', type=float, nargs='*', action=SM)
    input_group.add_argument('-c', '--channel', help='Channel number. Default: 0', default=0, type=int, action=SM)
    input_group.add_argument('-x', '--xy_res', help='xy resolution (e.g., in microns) for input .tif, .zarr, or .h5 files.', type=float, action=SM)
    input_group.add_argument('-z', '--z_res', help='z resolution (e.g., in microns) for input .tif, .zarr, or .h5 files.', type=float, action=SM)

    resample_group = parser.add_argument_group('Optional arguments for resampling (MUST PROVIDE: -tr, -td, -sc, or -r)')
    resample_group.add_argument(
        '-tr', '--target_res',
        help='Target resolution (array axes 0, 1, 2 in microns) for resampling (can be isotropic [e.g., 50] or anisotropic [e.g., 200 10 10])',
        default=None, type=float, nargs='*', action=SM
    )
    resample_group.add_argument(
        '-td', '--target_dims',
        help='Target dimensions for resampling (x, y, z). E.g., 512 512 30',
        default=None, type=int, nargs='*', action=SM
    )
    resample_group.add_argument(
        '-sc', '--scale',
        help='Scaling factor (e.g., 0.5 or 2 or 0.5 1 1)',
        default=None, nargs='*', type=float, action=SM
    )
    resample_group.add_argument(
        '-r', '--reference',
        help='Use reference image to set resampling parameters and .nii.gz metadata.',
        default=None, action=SM
    )
    resample_group.add_argument(
        '-zo', '--zoom_order',
        help='Spline interpolation order (0-5). Default: 0 (nearest-neighbor). Use 1 for linear interpolation.',
        default=0, type=int, choices=range(6), action=SM
    )

    save_group = parser.add_argument_group('Optional arguments for saving')
    save_group.add_argument(
        '-s', '--save_as',
        help='Output format extension (nii.gz, .zarr, .tif, or .h5). Default: .nii.gz',
        default='.nii.gz',
        choices=['.nii.gz', '.tif', '.zarr', '.h5'],
        action=SM
    )
    save_group.add_argument(
        '-o', '--out_dir',
        help='Optional output directory. If not provided, saves alongside input (as input_name_resampled.ext).',
        default=None, action=SM
    )
    save_group.add_argument(
        '-n', '--output_name',
        help='Output filename, including the --save_as extension. Requires exactly one matched input. Use --out_dir for its directory.',
        default=None, action=SM
    )
    save_group.add_argument(
        '-d', '--dtype',
        help='Output data type. Default: input type for order 0, float32 otherwise.',
        default=None, action=SM
    )

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def as_xyz(values, name):
    """Return one or three finite, positive values as an xyz vector."""
    values = np.atleast_1d(values).astype(float)
    if values.size == 1:
        values = np.repeat(values, 3)
    if values.shape != (3,) or not np.all(np.isfinite(values) & (values > 0)):
        raise ValueError(f"{name} must contain one or three finite, positive values.")
    return values


def load_image(path, args, reference=False):
    """Return data (or a NIfTI proxy), an affine in mm, and a NIfTI header."""
    if str(path).lower().endswith(('.nii', '.nii.gz')):
        nii = nib.load(str(path))
        unit = nii.header.get_xyzt_units()[0]
        factor = {'unknown': 1, 'mm': 1, 'micron': 0.001, 'meter': 1000}[unit]
        affine = nii.affine.copy()
        affine[:3, :] *= factor
        img, header = nii.dataobj, nii.header.copy()
    else:
        # Legacy loaders need xy/z values even when only reading pixel data.
        override = args.input_res if not reference else None
        xy_res = override[0] if override is not None else args.xy_res
        z_res = override[2] if override is not None else args.z_res
        img, xy_res, z_res = load_3D_img(
            path, channel=args.channel, return_res=True,
            xy_res=xy_res, z_res=z_res, verbose=args.verbose,
        )
        spacing = override if override is not None else [xy_res, xy_res, z_res]
        spacing = as_xyz(spacing, 'Input resolution; supply --input_res if metadata is missing')
        affine, header = np.diag([*spacing / 1000, 1]), None

    if len(img.shape) != 3:
        raise ValueError(f"{path} must be a 3D image. Got shape {img.shape}.")

    if not reference:
        spacing = args.input_res
        if spacing is None and (args.xy_res is not None or args.z_res is not None):
            spacing = nib.affines.voxel_sizes(affine) * 1000
            if args.xy_res is not None:
                spacing[:2] = args.xy_res
            if args.z_res is not None:
                spacing[2] = args.z_res
        if spacing is not None:
            spacing = as_xyz(spacing, 'Input resolution')
            affine[:3, :3] *= spacing / 1000 / nib.affines.voxel_sizes(affine)

    return img, affine, header


def target_grid(shape, affine, args, reference=None):
    """Define the output grid without changing the source orientation or origin."""
    if reference is not None:
        return reference[0].shape, reference[1].copy()

    shape = np.asarray(shape)
    spacing = nib.affines.voxel_sizes(affine)
    if args.target_dims is not None:
        target_shape = np.asarray(args.target_dims)
        ratio = shape / target_shape
    else:
        ratio = args.target_res / 1000 / spacing if args.target_res is not None else 1 / args.scale
        target_shape = np.rint(shape / ratio).astype(int)
    if np.any(target_shape < 1):
        raise ValueError('Target resolution/scale produces an empty axis. Use a finer resolution.')

    target_affine = affine.copy()
    target_affine[:3, :3] *= ratio
    return tuple(target_shape), target_affine


def resample_image(img, affine, shape, target_affine, order, dtype):
    """Sample output voxel centers at their corresponding source coordinates."""
    transform = np.linalg.solve(affine, target_affine)
    # Avoid floating-point noise at boundaries of otherwise identical grids.
    rounded = np.rint(transform)
    transform = np.where(np.abs(transform - rounded) < 1e-10, rounded, transform)
    return affine_transform(
        np.asanyarray(img), transform[:3, :3], offset=transform[:3, 3],
        output_shape=shape, output=np.dtype(dtype), order=order,
        mode='constant', cval=0, prefilter=order > 1,
    )


def save_image(img, output, affine, header, verbose=False):
    """Save all three voxel sizes without the legacy xy_res restriction."""
    output.parent.mkdir(parents=True, exist_ok=True)
    spacing = nib.affines.voxel_sizes(affine) * 1000
    if str(output).endswith('.nii.gz'):
        header = header.copy() if header is not None else nib.Nifti1Header()
        header.set_xyzt_units('mm')
        nii = nib.Nifti1Image(img, affine, header)
        nii.set_data_dtype(img.dtype)
        nii.set_sform(affine, code=int(header['sform_code']) or 2)
        try:
            nii.set_qform(affine, code=int(header['qform_code']) or 1, strip_shears=False)
        except nib.spatialimages.HeaderDataError:
            nii.set_qform(None, code=0)  # Shears are represented only by the sform.
        nii.header.set_slope_inter(1, 0)
        nib.save(nii, str(output))
    elif output.suffix == '.tif':
        import tifffile
        tifffile.imwrite(
            str(output), img.transpose(2, 1, 0), ome=True, photometric='minisblack',
            metadata=dict(axes='ZYX', PhysicalSizeX=spacing[0], PhysicalSizeY=spacing[1],
                          PhysicalSizeZ=spacing[2], PhysicalSizeXUnit='µm',
                          PhysicalSizeYUnit='µm', PhysicalSizeZUnit='µm'),
        )
    elif output.suffix == '.h5':
        import h5py
        with h5py.File(output, 'w') as f:
            dataset = f.create_dataset('data', data=img.transpose(2, 1, 0), compression='lzf')
            dataset.attrs['element_size_um'] = spacing[::-1]
    else:
        import zarr
        save_3D_img(img, output, verbose=verbose)
        zarr.open(str(output), mode='a').attrs['multiscales'] = [{
            'version': '0.4',
            'axes': [{'name': axis, 'type': 'space', 'unit': 'micrometer'} for axis in 'zyx'],
            'datasets': [{'path': '.', 'coordinateTransformations': [
                {'type': 'scale', 'scale': spacing[::-1].tolist()},
            ]}],
        }]
    print(f"\n    Output: [default bold]{output.resolve()}")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if sum(value is not None for value in (args.target_res, args.target_dims, args.scale, args.reference)) != 1:
        raise ValueError('Specify exactly one of --target_res, --target_dims, --scale, or --reference.')
    for name in ('target_res', 'scale', 'input_res'):
        if getattr(args, name) is not None:
            setattr(args, name, as_xyz(getattr(args, name), name))
    if args.target_dims is not None:
        if len(args.target_dims) != 3 or min(args.target_dims) < 1:
            raise ValueError('Target dimensions must contain three positive integers.')
    if args.input_res is not None and (args.xy_res is not None or args.z_res is not None):
        raise ValueError('Use --input_res or --xy_res/--z_res, not both.')

    image_paths = match_files(args.input)
    if args.output_name is not None:
        if len(image_paths) != 1:
            raise ValueError('--output_name requires exactly one matched input file.')
        if Path(args.output_name).name != args.output_name:
            raise ValueError('--output_name must be a filename. Use --out_dir for its directory.')
        if not args.output_name.endswith(args.save_as):
            raise ValueError(f'--output_name must end with {args.save_as}, as selected by --save_as.')

    reference = load_image(args.reference, args, reference=True) if args.reference else None
    for image_path in image_paths:
        image_path = Path(image_path)
        output_dir = Path(args.out_dir) if args.out_dir else image_path.parent
        filename = args.output_name or (get_stem(image_path) + '_resampled' + args.save_as)
        output = output_dir / filename
        if output.resolve() == image_path.resolve():
            raise ValueError('Output must differ from the input file.')
        img, affine, header = load_image(image_path, args)
        shape, target_affine = target_grid(img.shape, affine, args, reference)
        # Materialize NIfTI scaling before choosing an output dtype.
        img = np.asanyarray(img)
        dtype = args.dtype or (img.dtype if args.zoom_order == 0 else np.float32)
        result = resample_image(img, affine, shape, target_affine, args.zoom_order, dtype)
        if args.verbose:
            print(f"\n    Original shape: {img.shape}; resampled shape: {result.shape}")
            print(f"    Voxel sizes (µm): {tuple(nib.affines.voxel_sizes(target_affine) * 1000)}")
        save_image(result, output, target_affine, reference[2] if reference else header, args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()
