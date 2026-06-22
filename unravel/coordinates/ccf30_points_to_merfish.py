#!/usr/bin/env python3

"""
Use ``coords_ccf30_points_to_merfish`` or ``ccf30_points_to_merfish`` from UNRAVEL 
to transform CCFv3 30 µm point coordinates into MERFISH-CCF space using ANTs point transforms.

This is the point-coordinate analogue of ``warp_ccf30_to_merfish``. It should
be used instead of warping sparse labeled point images, because sparse labels
can be dropped or merged during image resampling/warping.

Input:
    - CSV with CCF30 voxel coordinates, e.g. x, y, z
    - CCF30 moving image used as the coordinate reference
    - CCF30_to_MERFISH warp root

Output:
    - CSV with original columns plus transformed MERFISH coordinates:
        ccf30_x, ccf30_y, ccf30_z
        ccf30_phys_ras_x/y/z
        ccf30_phys_lps_x/y/z
        merfish_phys_lps_x/y/z
        merfish_phys_ras_x/y/z
        merfish_padded_x/y/z
        merfish_x, merfish_y, merfish_z
        merfish_in_bounds

Notes:
    - Input x/y/z are assumed to be CCF30 voxel coordinates.
    - ANTs point transforms use physical coordinates in LPS space.
    - NIfTI affines from nibabel are treated as RAS; by default this script
      converts RAS <-> LPS around the ANTs point transform.
    - Image resampling and point transforms use opposite transform directions
      in ANTs. For moving CCF30 points -> fixed MERFISH points, this script
      uses:
          initial transform inverted
          affine transform inverted
          inverse warp
    - The final MERFISH voxel coordinates are cropped to match the unpadded
      MERFISH_resampled_average_template.nii.gz dimensions, matching the
      behavior of warp_ccf30_to_merfish / forward_warp.

Usage:
------
    coords_ccf30_points_to_merfish \\
        -i unique_voxels_CCF30_coords.csv \\
        -m CCF30/atlas_CCFv3_2020_30um.nii.gz \\
        -w /path/to/MERFISHf_CCF30m \\
        -x x -y y -z z \\
        -o unique_voxels_MERFISH_coords.csv \\
        -v
"""

from pathlib import Path

import ants
import nibabel as nib
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.coordinates.physical_points_to_img import validate_columns


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Input CSV with CCF30 voxel coordinates.", required=True, action=SM)
    reqs.add_argument("-m", "--moving_img", help="CCF30 moving image used as coordinate reference.", required=True, action=SM)
    reqs.add_argument("-w", "--warp_root", help="Path to CCF30_to_MERFISH warp root.", required=True, action=SM)

    coord_args = parser.add_argument_group("Coordinate arguments")
    coord_args.add_argument("-x", "--x_col", help="CCF30 voxel x column. Default: x", default="x", action=SM)
    coord_args.add_argument("-y", "--y_col", help="CCF30 voxel y column. Default: y", default="y", action=SM)
    coord_args.add_argument("-z", "--z_col", help="CCF30 voxel z column. Default: z", default="z", action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-o", "--output", help="Output CSV. Default: input stem + _MERFISH.csv", default=None, action=SM)
    opts.add_argument("-f", "--filter", help="Optional pandas query string.", default=None, action=SM)
    opts.add_argument(
        "-pad",
        "--pad_percent",
        help="Padding percentage used for MERFISH registration input. Default: 0.15",
        default=0.15,
        type=float,
        action=SM,
    )
    opts.add_argument(
        "--no-lps-conversion",
        help="Do not convert RAS <-> LPS around ANTs point transform. Default: False",
        action="store_true",
        default=False,
    )
    opts.add_argument(
        "--physical-input",
        help="Input coordinates are already physical RAS coordinates, not voxel coordinates. Default: False",
        action="store_true",
        default=False,
    )

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def _flip_xy(points):
    """Flip x and y coordinates for RAS <-> LPS conversion.
    
    Parameters:
    -----------
    points : ndarray
        An Nx3 array of physical coordinates in RAS or LPS space.
        
    Returns:
    --------
    ndarray
        An Nx3 array of physical coordinates with x and y flipped.
    """

    out = points.copy()
    out[:, 0] *= -1  # Flip x for RAS <-> LPS
    out[:, 1] *= -1  # Flip y for RAS <-> LPS
    return out

def ras_to_lps(points):
    """Convert Nx3 RAS physical coordinates to LPS."""
    return _flip_xy(points)

def lps_to_ras(points):
    """Convert Nx3 LPS physical coordinates to RAS."""
    return _flip_xy(points)


def voxel_to_physical_ras(voxel_coords, affine):
    """Convert Nx3 voxel coordinates to physical RAS coordinates."""
    return nib.affines.apply_affine(affine, voxel_coords)


def physical_ras_to_voxel(phys_coords, affine):
    """Convert Nx3 physical RAS coordinates to voxel coordinates."""
    inv_affine = np.linalg.inv(affine)
    return nib.affines.apply_affine(inv_affine, phys_coords)


def calculate_padded_dimensions(original_dimensions, pad_percent=0.15):
    """Match UNRAVEL forward_warp padding calculation."""
    padded_dimensions = []
    for dim in original_dimensions:
        pad_width_one_side = np.round(pad_percent * dim)
        total_padding = 2 * pad_width_one_side
        padded_dimensions.append(int(dim + total_padding))
    return np.array(original_dimensions), np.array(padded_dimensions)


def get_point_transformlist_moving_to_fixed(reg_outputs_path):
    """
    Return transform list for mapping moving-space points to fixed-space points.

    This is the point-transform analogue of moving image -> fixed image warping.
    Because ANTs point transforms go opposite to image resampling, this uses the
    inverse-warp style list.
    """
    reg_outputs_path = Path(reg_outputs_path)

    transforms_prefix_file = next(reg_outputs_path.glob("*1Warp.nii.gz"), None)
    if transforms_prefix_file is None:
        raise FileNotFoundError(f"No '*1Warp.nii.gz' file found in {reg_outputs_path}")

    transforms_prefix = transforms_prefix_file.name.replace("1Warp.nii.gz", "")

    inverse_warp = reg_outputs_path / f"{transforms_prefix}1InverseWarp.nii.gz"
    generic_affine = reg_outputs_path / f"{transforms_prefix}0GenericAffine.mat"
    initial_transform = reg_outputs_path / f"{transforms_prefix}init_tform.mat"

    if not initial_transform.exists():
        initial_transform = reg_outputs_path / "init_tform.mat"

    missing = [p for p in [inverse_warp, generic_affine, initial_transform] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing transform file(s): {missing}")

    transformlist = [
        str(initial_transform),
        str(generic_affine),
        str(inverse_warp),
    ]
    whichtoinvert = [True, True, False]

    return transformlist, whichtoinvert


def apply_ants_point_transform(points_lps, transformlist, whichtoinvert, verbose=False):
    """Apply ANTs point transform to physical LPS coordinates."""
    points_df = pd.DataFrame(points_lps, columns=["x", "y", "z"])

    transformed = ants.apply_transforms_to_points(
        dim=3,
        points=points_df,
        transformlist=transformlist,
        whichtoinvert=whichtoinvert,
        verbose=verbose,
    )

    return transformed[["x", "y", "z"]].to_numpy(dtype=float)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    moving_img_path = Path(args.moving_img)
    warp_root = Path(args.warp_root)

    fixed_img_path = warp_root / "MERFISH_resampled_average_template.nii.gz"
    fixed_reg_in_path = warp_root / "reg_outputs" / "MERFISH_resampled_average_template_fixed_reg_input.nii.gz"
    reg_outputs_path = warp_root / "reg_outputs"

    if not fixed_img_path.exists():
        raise FileNotFoundError(f"Missing fixed MERFISH image: {fixed_img_path}")
    if not fixed_reg_in_path.exists():
        raise FileNotFoundError(f"Missing fixed registration input: {fixed_reg_in_path}")
    if not reg_outputs_path.exists():
        raise FileNotFoundError(f"Missing reg_outputs directory: {reg_outputs_path}")

    df = pd.read_csv(input_path)

    if args.filter:
        if args.verbose:
            print(f"\n[blue]Filtering rows using filter:[/] {args.filter}")
            print(f"    Original rows: {len(df)}")
        df = df.query(args.filter).copy()
        if args.verbose:
            print(f"    Remaining rows: {len(df)}\n")

    validate_columns(df, [args.x_col, args.y_col, args.z_col])

    moving_nii = nib.load(moving_img_path)
    fixed_nii = nib.load(fixed_img_path)
    fixed_reg_nii = nib.load(fixed_reg_in_path)

    input_coords = df[[args.x_col, args.y_col, args.z_col]].to_numpy(dtype=float)

    out_df = df.copy()

    # NIfTI (nibabel) uses an RAS+ world coordinate convention, whereas ANTs expects LPS.
    # We therefore convert coordinates around the ANTs transform as:
    # voxel → physical (RAS) → convert to LPS → apply ANTs transform → convert back to RAS → voxel

    if args.physical_input:
        ccf30_phys_ras = input_coords
    else:
        ccf30_phys_ras = voxel_to_physical_ras(input_coords, moving_nii.affine)

    if args.no_lps_conversion:
        ccf30_phys_lps = ccf30_phys_ras.copy()
    else:
        ccf30_phys_lps = ras_to_lps(ccf30_phys_ras)

    transformlist, whichtoinvert = get_point_transformlist_moving_to_fixed(reg_outputs_path)

    if args.verbose:
        print("\n[bold]Using point transform list for moving CCF30 points -> fixed MERFISH points:[/]")
        for t, inv in zip(transformlist, whichtoinvert):
            print(f"    invert={inv}: {t}")

    merfish_phys_lps = apply_ants_point_transform(
        ccf30_phys_lps,
        transformlist=transformlist,
        whichtoinvert=whichtoinvert,
        verbose=args.verbose,
    )

    # Convert back to RAS for downstream processing and output, since nibabel affines are RAS
    if args.no_lps_conversion:
        merfish_phys_ras = merfish_phys_lps.copy()
    else:
        merfish_phys_ras = lps_to_ras(merfish_phys_lps)

    # Convert transformed physical coordinates to voxel coordinates in the
    # padded fixed registration input, then crop to unpadded MERFISH template.
    merfish_padded_vox = physical_ras_to_voxel(merfish_phys_ras, fixed_reg_nii.affine)

    original_dims = np.array(fixed_nii.shape[:3])
    _, padded_dims = calculate_padded_dimensions(original_dims, pad_percent=args.pad_percent)
    crop_mins = (padded_dims - original_dims) // 2

    merfish_vox = merfish_padded_vox - crop_mins

    merfish_vox_round = np.rint(merfish_vox).astype(int)

    in_bounds = (
        (merfish_vox_round[:, 0] >= 0) & (merfish_vox_round[:, 0] < original_dims[0]) &
        (merfish_vox_round[:, 1] >= 0) & (merfish_vox_round[:, 1] < original_dims[1]) &
        (merfish_vox_round[:, 2] >= 0) & (merfish_vox_round[:, 2] < original_dims[2])
    )

    out_df["merfish_x"] = merfish_vox_round[:, 0]
    out_df["merfish_y"] = merfish_vox_round[:, 1]
    out_df["merfish_z"] = merfish_vox_round[:, 2]
    out_df["merfish_in_bounds"] = in_bounds

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + "_MERFISH.csv")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)

    print(f"\n    Input rows: {len(df)}")
    print(f"    Moving image shape: {moving_nii.shape[:3]}")
    print(f"    Fixed MERFISH image shape: {tuple(original_dims)}")
    print(f"    Fixed reg input shape: {fixed_reg_nii.shape[:3]}")
    print(f"    Crop mins: {crop_mins.tolist()}")
    print(f"    MERFISH in-bounds rows: {int(in_bounds.sum())}")
    print(f"    MERFISH out-of-bounds rows: {int((~in_bounds).sum())}")
    print(f"    Output CSV saved to: {output_path}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()