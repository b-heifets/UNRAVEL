#!/usr/bin/env python3

"""
Use ``conv_czi_with_alt_loader.py`` to load a .czi image where each slice was stitched separately and save as a different format.

This script reads every plane into the same full-resolution XY rectangle, preserves the recorded tile positions, and avoids changing dimensions across Z. 
It does not correct actual misalignment introduced by independent stitching.

Prereqs:
    - Install pylibCZIrw in the Python environment used to run this script:
        python -m pip install pylibCZIrw==6.1.0

Input image types:
    - .czi

Output image types:
    - .tif series (provide a path to the dir where the .tif files will be saved)
    - .zarr
    - .h5

Usage:
------
    ./conv_czi_with_alt_loader.py -i 'sample.czi' -c 1 -s .tif [-o output_dir] [-d uint16] [-v]

"""

import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from pylibCZIrw import czi as czi_rw

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import return_3D_img, save_3D_img, save_metadata_to_file
from unravel.core.utils import get_stem, initialize_progress_bar, log_command, match_files, print_func_name_args_times, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Glob pattern(s) for input image files. Default: '*.czi'.", nargs='*', default='*.czi', action=SM)
    opts.add_argument('-s', '--save_as', help='Output format extension (.tif, .zarr, .h5). Default: .tif', choices=[ '.tif', '.zarr', '.h5'], default='.tif', action=SM)
    opts.add_argument('-c', '--channel', help='Channel number. Default: 0', default=0, type=int, action=SM)
    opts.add_argument('-o', '--output', help='Output directory for converted images. Default: same as input file location', default=None, action=SM)
    opts.add_argument('-d', '--dtype', help='Output data type. Options: uint8, uint16, float32 (numpy conventions).', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def _czi_layout(reader, channel):
    """Get full-resolution geometry from subblock headers, without pixel reads."""
    if not isinstance(channel, (int, np.integer)) or channel < 0:
        raise ValueError('CZI channel must be a nonnegative integer.')
    if not hasattr(reader, 'enumerate_subblocks_subset'):
        raise RuntimeError('This CZI loader requires pylibCZIrw 6.1.0 or newer.')

    records = []

    def collect(index, info):
        records.append((info.coordinate.to_dict(), str(info.pixelType).split('.')[-1]))
        return True

    reader.enumerate_subblocks_subset(collect, only_layer0=True)
    if not records:
        raise ValueError('CZI contains no full-resolution image subblocks.')
    axes = set().union(*(coords for coords, _ in records))
    values = {axis: {coords.get(axis, 0) for coords, _ in records} for axis in axes}
    # The existing API selects a channel, but has no scene/time/view selectors.
    ambiguous = {axis: sorted(vals) for axis, vals in values.items()
                 if axis not in ('C', 'Z') and len(vals) > 1}
    if ambiguous:
        raise ValueError(f'CZI is not a single 3D volume per channel: {ambiguous}. '
                         'Export the desired scene/time/view separately.')
    channels = sorted(values.get('C', {0}))
    if channel not in channels:
        raise ValueError(f'CZI channel {channel} is absent; available channels: {channels}.')
    selected = [(coords, kind) for coords, kind in records if coords.get('C', 0) == channel]
    z_indices = sorted({coords.get('Z', 0) for coords, _ in selected})
    z_start, z_stop = z_indices[0], z_indices[-1] + 1
    if len(z_indices) != z_stop - z_start:
        raise ValueError('Selected CZI channel has missing Z planes; refusing to collapse the Z axis.')
    pixel_types = {kind for _, kind in selected}
    supported = {'Gray8': 'uint8', 'Gray16': 'uint16', 'Gray32Float': 'float32'}
    if len(pixel_types) != 1 or not pixel_types.issubset(supported):
        raise ValueError(f'Expected one grayscale pixel type per channel; got {sorted(pixel_types)}.')
    pixel_type = next(iter(pixel_types))

    # Use one layer-0 rectangle across all Z planes and channels. This preserves
    # tile placement and channel alignment, including nonzero/negative XY origins.
    rect = reader.total_bounding_rectangle_no_pyramid
    if rect.w <= 0 or rect.h <= 0:
        raise ValueError(f'Invalid full-resolution CZI rectangle: {rect}.')
    coords = selected[0][0]
    return {
        'shape_zyx': (len(z_indices), rect.h, rect.w),
        'roi_xywh': (rect.x, rect.y, rect.w, rect.h),
        'z_bounds': (z_start, z_stop),
        'scene': coords.get('S'),
        'plane': {axis: int(value) for axis, value in coords.items() if axis != 'S'},
        'pixel_type': pixel_type,
        'dtype': supported[pixel_type],
        'channel': int(channel),
        'full_resolution_subblocks': len(selected),
    }


def inspect_czi(czi_path, channel=0):
    """Return CZI geometry without decoding pixels or allocating the 3D image.

    ``shape_zyx`` is the rendered layer-0 shape. ``xml_size_xyz`` contains the
    descriptive XML sizes for comparison; it is not used to reshape pixels.
    Requires pylibCZIrw 6.1.0 or newer.
    """
    with czi_rw.open_czi(str(czi_path)) as reader:
        layout = _czi_layout(reader, channel)
        root = ET.fromstring(reader.raw_metadata)
        layout['xml_size_xyz'] = tuple(
            root.findtext(f'.//Information/Image/Size{axis}') for axis in 'XYZ')
    return layout


@print_func_name_args_times()
def load_czi(czi_path, channel=0, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None, verbose=False):
    """Load a grayscale CZI channel through fixed-rectangle, full-resolution planes.

    Requires ``python -m pip install pylibCZIrw==6.1.0``. This replaces the
    aicspylibczi bulk ``read_image`` path. Each plane is rendered by the ZEISS
    reader at zoom=1.0, checked, and copied into a NumPy-owned ZYX volume.
    The complete channel still has to fit in RAM, plus one rendered XY plane.

    The rectangle is shared across all channels and Z planes, using layer-0
    bounds to exclude pyramid padding. Missing XY tile coverage is black.
    Multiple scenes/timepoints/views and missing Z planes raise ValueError.
    Singleton spatial axes are retained; no unrestricted squeeze or reshape.

    Return conventions match the original function: image alone, image plus
    (xy_res, z_res), or image plus (xy_res, z_res, x_dim, y_dim, z_dim).
    Resolutions are micrometers. Dimension metadata always uses actual XYZ
    sizes, regardless of the requested ndarray axis order.
    """
    if desired_axis_order not in ('xyz', 'zyx'):
        raise ValueError('desired_axis_order must be "xyz" or "zyx".')

    with czi_rw.open_czi(str(czi_path)) as reader:
        layout = _czi_layout(reader, channel)
        z_dim, y_dim, x_dim = layout['shape_zyx']
        dtype = np.dtype(layout['dtype'])
        if verbose:
            gib = z_dim * y_dim * x_dim * dtype.itemsize / 2**30
            print(f'    CZI layer-0 ZYX: {(z_dim, y_dim, x_dim)}; {dtype}; {gib:.2f} GiB', flush=True)
            print(f'    Fixed ROI (x, y, width, height): {layout["roi_xywh"]}; '
                  f'Z bounds: {layout["z_bounds"]}; channel: {channel}', flush=True)

        if return_res or return_metadata or save_metadata:
            root = ET.fromstring(reader.raw_metadata)

            def resolution_um(axis):
                value = root.findtext(f".//Scaling/Items/Distance[@Id='{axis}']/Value")
                if value is None:
                    return None
                value = float(value) * 1e6
                if not np.isfinite(value) or value <= 0:
                    return None
                return value

            if xy_res is None:
                xy_res = resolution_um('X')
                y_res = resolution_um('Y')
                if xy_res is not None and y_res is not None and not np.isclose(xy_res, y_res):
                    raise ValueError(f'CZI has unequal X/Y voxel sizes ({xy_res}, {y_res}) um; '
                                     'the existing xy_res API cannot represent both.')
            if z_res is None:
                z_res = resolution_um('Z')

        volume = np.empty((z_dim, y_dim, x_dim), dtype=dtype)
        plane_coords = dict(layout['plane'])
        plane_coords['C'] = int(channel)
        for out_z, source_z in enumerate(range(*layout['z_bounds'])):
            plane_coords['Z'] = source_z
            plane = reader.read(
                roi=layout['roi_xywh'], plane=plane_coords, scene=layout['scene'],
                zoom=1.0, pixel_type=layout['pixel_type'], background_pixel=(0.0, 0.0, 0.0))
            if plane.shape != (y_dim, x_dim, 1) or plane.dtype != dtype:
                raise ValueError(f'CZI Z={source_z}: expected {(y_dim, x_dim, 1)} {dtype}; '
                                 f'got {plane.shape} {plane.dtype}.')
            np.copyto(volume[out_z], plane[..., 0], casting='no')
            del plane
            if verbose and (out_z == 0 or (out_z + 1) % max(1, z_dim // 10) == 0 or out_z + 1 == z_dim):
                print(f'    CZI planes: {out_z + 1}/{z_dim}', flush=True)

    ndarray = volume.transpose(2, 1, 0) if desired_axis_order == 'xyz' else volume
    if save_metadata:
        save_metadata_to_file(xy_res, z_res, x_dim, y_dim, z_dim, save_metadata=save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img_files = match_files(args.input)
    
    # Make sure the output directory exists
    if args.output:
        Path(args.output).mkdir(parents=True, exist_ok=True)

    progress, task_id = initialize_progress_bar(len(img_files), task_message="[bold green]Converting images...")
    with Live(progress):

        for img_file in img_files:
            if img_file.suffix.lower() == '.czi':
                img, xy_res, z_res = load_czi(img_file, channel=args.channel, return_res=True, verbose=args.verbose)

                img_file_basename = get_stem(img_file.name)

                # Define output path based on the input file name and specified output format
                if args.save_as == '.tif':
                    out_path = img_file.parent / img_file_basename if not args.output else Path(args.output) / img_file_basename
                else:
                    # For other formats, use the same directory as the input file
                    out_dir_path = img_file.parent if not args.output else Path(args.output)
                    out_path = out_dir_path / f"{img_file_basename}{args.save_as}"
            else:
                raise ValueError(f"Unsupported input format: {img_file.suffix}. Only .czi is supported.")

            save_3D_img(img, output_path=out_path, ndarray_axis_order="xyz", xy_res=xy_res, z_res=z_res, data_type=args.dtype, verbose=args.verbose)


    verbose_end_msg()


if __name__ == '__main__':
    main()