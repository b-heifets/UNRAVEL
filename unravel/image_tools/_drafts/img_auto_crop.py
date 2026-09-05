#!/usr/bin/env python3

"""
Use ``img_auto_crop`` to make full-resolution MIPs, predict a padded brain
bounding box, and save the original image subset as a TIFF series.

Inputs:
    - Any 3D image supported by load_3D_img(), including a selected CZI channel.
    - A MIP intensity threshold, a bounding-box string, or a bounding-box file.

Outputs (all within -o):
    - mip/mip_z.tif, mip_y.tif, mip_x.tif: unscaled, original-dtype MIPs.
    - mip/mask_*.tif: selected thresholded components (automatic mode).
    - mip/preview_*.tif: 8-bit RGB previews; yellow mask outline,
      magenta detected box, green final/padded box.
    - bbox_zyx.txt, bbox_pad_zyx.txt: zero-based, stop-exclusive bounds.
    - crop.json: source, geometry, parameters, and processing status.
    - slice_0000.tif, ...: original-dtype XY slices, unless preview-only.

Notes:
    - No resampling, full-volume threshold mask, or full-volume dtype conversion.
      The complete selected channel must still fit in RAM: load_3D_img() does
      not read only the CZI subset. This does not fix CZI loading errors.
    - Arrays and bbox files use ZYX order: zmin:zmax, ymin:ymax, xmin:xmax.
      mip_z: rows Y / columns X; mip_y: Z / X; mip_x: Z / Y.
    - With no threshold or box, only MIPs and metadata are saved. Choose a
      threshold from the raw MIPs; an AIP threshold is not directly transferable.
    - Automatic detection keeps the largest 4-connected component in each MIP
      (or all foreground with --keep_all). Bounds from the two views of each
      axis are combined using their union, then padded and clipped to the image.
      Independent components can represent different objects; inspect previews.
    - -pad is a fraction added on EACH side of a detected box (0.05 = 5%%).
      Supplied boxes are used AS-IS, with no extra padding. Edit/reuse the
      bbox_pad_zyx.txt file for manual corrections or aligned channels.
    - -f preserves an existing output directory as a timestamped backup, and
      publishes the new directory only after writing finishes. Failed TIFF
      exports leave the previous output intact. Allow space for the new export.
    - Plain TIFF slices do not carry voxel calibration from save_as_tifs();
      available voxel sizes and the crop origin are recorded in crop.json.

Usage:
------
    python img_auto_crop.py -i '*.czi' -c 0 -o brain_c0
    python img_auto_crop.py -i '*.czi' -c 0 -o brain_c0 -t 500 -pad 0.05 -n -f
    python img_auto_crop.py -i '*.czi' -c 0 -o brain_c0 -bf brain_c0/bbox_pad_zyx.txt -f
    python img_auto_crop.py -i '*.czi' -c 1 -o brain_c1 -bf brain_c0/bbox_pad_zyx.txt

The example threshold is illustrative, not a recommended value for your data.
"""

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import tifffile
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import binary_erosion, label

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.img_tools import crop
from unravel.core.utils import (
    get_samples, get_stem, initialize_progress_bar, log_command, match_files,
    print_func_name_args_times, verbose_start_msg, verbose_end_msg,
)


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', required=True, action=SM,
                      help='Image path or glob relative to each sample. First match used.')

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', default=None, action=SM,
                      help='Output directory relative to each sample. Default: <input_stem>_c<channel>_cropped')
    opts.add_argument('-c', '--channel', default=0, type=int, action=SM,
                      help='Channel to load. Default: 0')
    mode = opts.add_mutually_exclusive_group()
    mode.add_argument('-t', '--threshold', type=float, nargs='+', action=SM,
                      help='One threshold for all MIPs, or three in Z Y X projection order. Omit for MIPs only.')
    mode.add_argument('-b', '--bbox', action=SM,
                      help='Final box in ZYX order: "zmin:zmax, ymin:ymax, xmin:xmax". No additional padding.')
    mode.add_argument('-bf', '--bbox_file', action=SM,
                      help='Text file containing a final ZYX box, relative to each sample. No additional padding.')
    opts.add_argument('-pad', '--pad_percent', default=0.05, type=float, action=SM,
                      help='Fraction added to EACH side of the automatic box. Default: 0.05 (5%%)')
    opts.add_argument('--keep_all', action='store_true',
                      help='Use all thresholded foreground instead of the largest component.')
    opts.add_argument('-n', '--preview_only', action='store_true',
                      help='Save MIPs, masks, boxes, and previews without exporting the TIFF series.')
    opts.add_argument('-w', '--workers', default=4, type=int, action=SM,
                      help='TIFF-writing workers. Default: 4. Use 1 for sequential writes.')
    opts.add_argument('-f', '--force', action='store_true',
                      help='Replace output, keeping the previous directory as a timestamped backup.')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', nargs='*', default=None, action=SM,
                         help='Sample directories and/or directories containing them. Default: current directory')
    general.add_argument('-p', '--pattern', default='sample??', action=SM,
                         help='Sample directory pattern. Default: sample??')
    general.add_argument('-v', '--verbose', action='store_true',
                         help='Increase verbosity.')
    args = parser.parse_args()
    if args.channel < 0 or args.workers < 1:
        parser.error('--channel must be nonnegative and --workers must be positive.')
    if not np.isfinite(args.pad_percent) or args.pad_percent < 0:
        parser.error('--pad_percent must be finite and nonnegative.')
    if args.threshold is not None:
        if len(args.threshold) not in (1, 3) or not np.isfinite(args.threshold).all():
            parser.error('--threshold needs one or three finite values (Z Y X).')
    elif args.keep_all:
        parser.error('--keep_all requires --threshold.')
    return args


@print_func_name_args_times()
def make_mips(img):
    """Exact NumPy reductions of a ZYX volume; only 2D outputs are allocated."""
    if img.ndim != 3 or 0 in img.shape or img.dtype.kind not in 'buif':
        raise ValueError('Input must be a nonempty, real-valued 3D ndarray.')
    mips = {name: np.max(img, axis=axis) for axis, name in enumerate('zyx')}
    if any(not np.isfinite(mip).all() for mip in mips.values()):
        raise ValueError('MIPs contain NaN or infinity; check the input image.')
    return mips


def component_bbox(mip, threshold, keep_all=False):
    """Threshold one MIP and find row/column bounds without voxel-coordinate lists."""
    mask = mip > threshold
    if not mask.any():
        raise ValueError(f'No foreground above threshold {threshold:g}.')
    if not keep_all:
        labels, _ = label(mask)  # Default 2D structure is 4-connected.
        counts = np.bincount(labels.ravel())
        counts[0] = 0
        mask = labels == counts.argmax()
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    bbox = ((int(rows[0]), int(rows[-1]) + 1),
            (int(cols[0]), int(cols[-1]) + 1))
    return bbox, mask


@print_func_name_args_times()
def predict_bbox(mips, thresholds, keep_all=False):
    """Union corresponding intervals from all three independently segmented MIPs."""
    thresholds = np.atleast_1d(thresholds)
    if len(thresholds) == 1:
        thresholds = np.repeat(thresholds, 3)
    if len(thresholds) != 3 or not np.isfinite(thresholds).all():
        raise ValueError('Provide one or three finite MIP thresholds in Z Y X order.')
    bounds, masks, plane_boxes = [[], [], []], {}, {}
    for projection_axis, name in enumerate('zyx'):
        try:
            box, masks[name] = component_bbox(mips[name], thresholds[projection_axis], keep_all)
        except ValueError as exc:
            raise ValueError(f'MIP {name.upper()}: {exc}') from exc
        plane_boxes[name] = box
        axes = [axis for axis in range(3) if axis != projection_axis]
        for axis, interval in zip(axes, box):
            bounds[axis].append(interval)
    bbox = tuple((min(pair[0] for pair in intervals), max(pair[1] for pair in intervals))
                 for intervals in bounds)
    return bbox, masks, plane_boxes


def format_bbox(bbox):
    """Text format shared with core.img_tools.crop() and gta_bbox_crop."""
    return ', '.join(f'{start}:{stop}' for start, stop in bbox)


def parse_bbox(text, shape):
    """Validate explicit half-open ZYX bounds; never silently wrap negative indices."""
    try:
        bbox = tuple(tuple(int(value) for value in pair.split(':')) for pair in text.strip().split(','))
        if len(bbox) != 3 or any(len(pair) != 2 for pair in bbox):
            raise ValueError
        if any(not 0 <= start < stop <= size for (start, stop), size in zip(bbox, shape)):
            raise ValueError
    except ValueError as exc:
        raise ValueError(f'Expected valid ZYX bounds within {tuple(shape)}: "zmin:zmax, ymin:ymax, xmin:xmax".') from exc
    return bbox


def pad_bbox(bbox, shape, fraction):
    """Expand by a fraction of each detected extent on each side, retaining source voxels."""
    padded = []
    for (start, stop), size in zip(bbox, shape):
        width = int(np.ceil((stop - start) * fraction))
        padded.append((max(0, start - width), min(size, stop + width)))
    return tuple(padded)


def make_preview(mip, bbox, padded_bbox, mask=None):
    """Full-size RGB display copy; never change the MIP or exported image intensities."""
    gray = mip.astype(np.float64)
    low, high = float(gray.min()), float(gray.max())
    gray -= low
    if high > low:
        gray *= 255.0 / (high - low)
    rgb = np.repeat(np.clip(gray, 0, 255).astype(np.uint8)[..., None], 3, axis=2)
    if mask is not None:
        rgb[mask & ~binary_erosion(mask)] = (255, 255, 0)
    for box, color in ((bbox, (255, 0, 255)), (padded_bbox, (0, 255, 0))):
        (r0, r1), (c0, c1) = box
        rgb[r0:r1, c0] = rgb[r0:r1, c1 - 1] = color
        rgb[r0, c0:c1] = rgb[r1 - 1, c0:c1] = color
    return rgb


def publish_output(staged, output, force):
    """Replace the whole output to avoid stale TIFF slices; preserve the old result."""
    backup = None
    if output.exists():
        if not force:
            raise FileExistsError(f'{output} exists. Use -f to preserve it as a backup and replace it.')
        backup = output.with_name(f'{output.name}.backup-{time.time_ns()}')
        output.rename(backup)
    try:
        staged.rename(output)
    except OSError:
        if backup is not None and not output.exists():
            backup.rename(output)
        raise
    if backup is not None:
        print(f'    Previous output preserved: {backup}')


def process_sample(sample_path, args):
    matches = match_files(args.input, base_path=sample_path)
    img_path = matches[0].resolve()
    if len(matches) > 1:
        print(f'    {len(matches)} matches; using {img_path.name}')
    output_path = sample_path / (args.output or f'{get_stem(img_path)}_c{args.channel}_cropped')
    if output_path.is_symlink():
        raise ValueError('Output must not be a symbolic link.')
    output = output_path.resolve()
    # Protect the input, sample, and their parents from being renamed/replaced.
    if output == sample_path or output in sample_path.parents or output == img_path or output in img_path.parents:
        raise ValueError('Output must not replace the input, sample directory, or an ancestor.')
    if img_path.is_dir() and img_path in output.parents:
        raise ValueError('Output must not be inside the input image directory/store.')
    if output.exists() and not output.is_dir():
        raise ValueError(f'Output is not a directory: {output}')
    if output.exists() and not args.force:
        print(f'    {output} exists. Skipping; use -f to preserve it as a backup and replace it.')
        return

    bbox_text = args.bbox
    if args.bbox_file:
        bbox_text = (sample_path / args.bbox_file).read_text()
    try:
        img, xy_res, z_res = load_3D_img(
            img_path, channel=args.channel, desired_axis_order='zyx',
            return_res=True, verbose=args.verbose)
    except SystemExit as exc:
        raise RuntimeError('load_3D_img() exited before returning an image; see its error above.') from exc
    mips = make_mips(img)
    print(f'    Loaded ZYX {img.shape}, {img.dtype}; image array {img.nbytes / 2**30:.2f} GiB')

    metadata = {
        'source': str(img_path), 'channel': args.channel, 'axis_order': 'zyx',
        'shape_zyx': list(img.shape), 'dtype': str(img.dtype),
        'voxel_size_um_zyx': [float(v) if v is not None else None for v in (z_res, xy_res, xy_res)],
        'bounds_convention': 'zero-based, stop-exclusive',
        'mip_axes_rows_columns': {'z': ['y', 'x'], 'y': ['z', 'x'], 'x': ['z', 'y']},
        'thresholds_zyx': args.threshold, 'keep_all': args.keep_all,
        'status': 'mips_only', 'tiff_series_saved': False,
    }
    bbox, padded_bbox, masks, error = None, None, {}, None
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.img_auto_crop-', dir=output.parent) as temp_dir:
        staged = Path(temp_dir) / 'result'
        mip_dir = staged / 'mip'
        mip_dir.mkdir(parents=True)
        for name, mip in mips.items():
            tifffile.imwrite(mip_dir / f'mip_{name}.tif', mip, photometric='minisblack')
        try:
            if bbox_text is not None:
                bbox = padded_bbox = parse_bbox(bbox_text, img.shape)
                metadata.update(mode='supplied_box', padding_fraction_per_side=0)
            elif args.threshold is not None:
                bbox, masks, plane_boxes = predict_bbox(mips, args.threshold, args.keep_all)
                padded_bbox = pad_bbox(bbox, img.shape, args.pad_percent)
                metadata.update(mode='automatic', padding_fraction_per_side=args.pad_percent,
                                mip_component_boxes=plane_boxes)
        except ValueError as exc:
            error = exc
            metadata.update(status='bbox_failed', error=str(exc))

        if padded_bbox is not None:
            (staged / 'bbox_zyx.txt').write_text(format_bbox(bbox) + '\n')
            (staged / 'bbox_pad_zyx.txt').write_text(format_bbox(padded_bbox) + '\n')
            metadata.update(bbox_zyx=bbox, bbox_pad_zyx=padded_bbox,
                            crop_origin_zyx=[pair[0] for pair in padded_bbox],
                            crop_shape_zyx=[stop - start for start, stop in padded_bbox], status='preview')
            for projection_axis, name in enumerate('zyx'):
                axes = [axis for axis in range(3) if axis != projection_axis]
                if name in masks:
                    tifffile.imwrite(mip_dir / f'mask_{name}.tif', masks[name].astype(np.uint8) * 255,
                                     photometric='minisblack')
                preview = make_preview(mips[name], [bbox[a] for a in axes],
                                       [padded_bbox[a] for a in axes], masks.get(name))
                tifffile.imwrite(mip_dir / f'preview_{name}.tif', preview, photometric='rgb')
            print(f'    Final ZYX box: {format_bbox(padded_bbox)}')
            if any(start == 0 or stop == size for (start, stop), size in zip(padded_bbox, img.shape)):
                print('    [yellow]Box reaches an input edge; inspect tissue coverage and available padding.[/yellow]')
            if not args.preview_only:
                img_cropped = crop(img, format_bbox(padded_bbox))  # Basic slicing: a view, not a 3D copy.
                save_as_tifs(img_cropped, staged, ndarray_axis_order='zyx',
                             parallel=args.workers > 1, max_workers=args.workers, verbose=args.verbose)
                metadata.update(status='exported', tiff_series_saved=True)
        (staged / 'crop.json').write_text(json.dumps(metadata, indent=2) + '\n')
        publish_output(staged, output, args.force)
    print(f'    Saved: {output}')
    if error is not None:
        raise ValueError(f'{error} No TIFF series exported. Inspect raw MIPs in {output / "mip"}.')
    if bbox is None:
        print('    MIPs only: inspect their raw intensities, then rerun with -t or a supplied box and -f.')


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    sample_paths = list(dict.fromkeys(get_samples(args.dirs, args.pattern, args.verbose)))
    if not sample_paths:
        raise ValueError('No sample directories found.')
    if len(sample_paths) > 1 and (Path(args.input).is_absolute() or
                                (args.output and Path(args.output).is_absolute())):
        raise ValueError('Use sample-relative input/output paths for batch processing.')
    failures = 0
    progress, task_id = initialize_progress_bar(len(sample_paths), '[red]Processing samples...')
    with Live(progress):
        for sample_path in sample_paths:
            print(f'\n    {sample_path}')
            try:
                process_sample(Path(sample_path).resolve(), args)
            except (OSError, ValueError, RuntimeError) as exc:
                failures += 1
                print(f'    [red]Failed:[/red] {exc}')
            finally:
                progress.update(task_id, advance=1)
    verbose_end_msg()
    if failures:
        raise SystemExit(f'{failures} sample(s) failed; see messages above.')


if __name__ == '__main__':
    main()
