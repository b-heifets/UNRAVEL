#!/usr/bin/env python3
"""
Use ``reg_adjust_template`` (``rat``) from UNRAVEL to adjust intensities in a template for a single set of atlas label IDs.

Note:
    - The boundary between the adjusted region and the rest of the image can be sharp or blurred by applying a Gaussian blur to a two-sided boundary band around the region.
    - The boundary band is computed as:
        inside band  = region - erosion(region, band_width)
        outside band = dilation(region, band_width) - region
        band = inside OR outside
    - We blur the full (modified) image, then replace only band voxels with blurred values.
    
Example of use (separate steps):
--------------------------------
# 1) Fiber tracts: scale by 0.85
reg_adjust_template -i template.nii.gz -a atlas.nii.gz -ids <FIBER_IDS...> --scale 0.85 -bb -o template_fibers.nii.gz

# 2) HPF: scale by 0.8 (using previous output)
reg_adjust_template -i template_fibers.nii.gz -a atlas.nii.gz -ids <HPF_IDS...> --scale 0.8 -bb -o template_fibers_hpf.nii.gz

# 3) DG/CAsp: scale by 2.0 (using previous output)
reg_adjust_template -i template_fibers_hpf.nii.gz -a atlas.nii.gz -ids <DG_CAsp_IDS...> --scale 2.0 -bb -o template_fibers_hpf_dg.nii.gz

Usage:
------
    reg_adjust_template -i path/image.nii.gz -a path/atlas_labels.nii.gz -ids <ID1> <ID2> ... -o path/output.nii.gz [--scale <factor> | --set <value>] [-bb -s <float> -bw <int>] [-dt <dtype>] [-v]
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, binary_erosion, binary_dilation
from rich.traceback import install
from rich import print

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_nii, save_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    p = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    req = p.add_argument_group('Required arguments')
    req.add_argument('-i', '--input', help='Input image (.nii.gz)', required=True, action=SM)
    req.add_argument('-a', '--atlas', help='Atlas label image (.nii.gz) in same space', required=True, action=SM)
    req.add_argument('-ids', '--label_IDs', help='Atlas label IDs defining the region to modify.', required=True, nargs='*', type=int, action=SM)
    req.add_argument('-o', '--output', help='Output image (.nii.gz)', required=True, action=SM)

    # Exactly one of these must be provided
    op = p.add_argument_group('Operation (choose one)')
    op.add_argument('--scale', help='Multiply region voxels by this factor.', type=float, default=None, action=SM)
    op.add_argument('--set', help='Set region voxels to this absolute value.', type=float, default=None, action=SM)

    opt = p.add_argument_group('Optional arguments')
    opt.add_argument('-bb', '--band_blur', help='Blur only a two-sided boundary band (inside+outside) around the region after modifying it.', action='store_true', default=False)
    opt.add_argument('-s', '--sigma', help='Gaussian sigma (voxels) used when --band_blur is set. Default: 1.0', type=float, default=1.0, action=SM)
    opt.add_argument('-bw', '--band_width', help='Boundary band thickness in voxels (>=1). Default: 1', type=int, default=1, action=SM)
    opt.add_argument('-dt', '--dtype', help='Optional dtype for output (e.g., uint16). If omitted, preserves input dtype.', default=None, action=SM)

    gen = p.add_argument_group('General arguments')
    gen.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return p.parse_args()


def mask_from_ids(atlas: np.ndarray, ids: list[int]) -> np.ndarray:
    """Binary mask where atlas label is in ids."""
    return np.isin(atlas, np.asarray(ids, dtype=atlas.dtype))


def boundary_band_mask(region_mask: np.ndarray, band_width: int = 1) -> np.ndarray:
    """
    Two-sided boundary band:
      inside band  = region - erode(region, n)
      outside band = dilate(region, n) - region
      band = inside OR outside
    """
    if band_width < 1:
        raise ValueError("--band_width must be >= 1")

    er = region_mask.copy()
    dl = region_mask.copy()
    for _ in range(band_width):
        er = binary_erosion(er)
        dl = binary_dilation(dl)

    inside = region_mask & (~er)
    outside = dl & (~region_mask)
    return inside | outside


def safe_cast_like(x: np.ndarray, dtype: np.dtype) -> np.ndarray:
    """Cast with rounding/clipping if integer."""
    dt = np.dtype(dtype)
    if np.issubdtype(dt, np.integer):
        info = np.iinfo(dt)
        x = np.rint(x)
        x = np.clip(x, info.min, info.max)
        return x.astype(dt)
    return x.astype(dt)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Enforce exactly one operation
    if (args.scale is None) == (args.set is None):
        raise ValueError("Specify exactly one of --scale or --set")

    img = load_nii(args.input)
    atlas = load_nii(args.atlas)

    if img.shape != atlas.shape:
        raise ValueError(f"Shape mismatch: input {img.shape} vs atlas {atlas.shape}")

    in_dtype = img.dtype
    work = img.astype(np.float32, copy=True)

    reg_mask = mask_from_ids(atlas, args.label_IDs)
    nvox = int(reg_mask.sum())
    if args.verbose:
        print(f"\nRegion voxels: {nvox}\n")

    # Modify region
    if args.scale is not None:
        if args.verbose:
            print(f"Scaling region by {args.scale}")
        work[reg_mask] *= float(args.scale)
    else:
        if args.verbose:
            print(f"Setting region to {args.set}")
        work[reg_mask] = float(args.set)

    # Optional two-sided band blur for that region
    if args.band_blur:
        band = boundary_band_mask(reg_mask, band_width=args.band_width)
        if args.verbose:
            print(
                f"Band voxels: {int(band.sum())} "
                f"(sigma={args.sigma}, band_width={args.band_width})"
            )
        blurred = gaussian_filter(work, sigma=args.sigma)
        work[band] = blurred[band]

    out_dtype = np.dtype(args.dtype) if args.dtype else in_dtype
    out = safe_cast_like(work, out_dtype)

    save_3D_img(out, args.output, reference_img=args.input, verbose=args.verbose)
    verbose_end_msg()


if __name__ == "__main__":
    main()
