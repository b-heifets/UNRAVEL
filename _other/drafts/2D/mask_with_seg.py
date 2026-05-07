#!/usr/bin/env python3

"""
Use ``_other/drafts/2D/mask_with_seg.py`` from UNRAVEL to set pixels in TIFF images
to a target intensity based on matching Ilastik segmentation TIFFs.

Usage:
------
    mask_with_seg.py -i 'path/*.tif' -s 'path/*_Segmentation.tif' \
        [-l 1] [-d 3] [-t 0] [-o masked] [-v]
"""

from pathlib import Path
import numpy as np
import tifffile
from rich import print
from rich.traceback import install
from scipy.ndimage import binary_dilation

from unravel.core.img_io import load_single_tif
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument(
        "-i", "--input",
        help="Path to input tif(s) or glob pattern.",
        nargs="*",
        required=True,
        action=SM,
    )
    reqs.add_argument(
        "-s", "--seg",
        help="Path to Ilastik segmentation tif(s) or glob pattern.",
        nargs="*",
        required=True,
        action=SM,
    )

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument(
        "-l", "--label",
        help="Segmentation label/intensity to use as the mask. Default: 1",
        default=1,
        type=int,
        action=SM,
    )
    opts.add_argument(
        "-t", "--target-intensity",
        help="Intensity assigned to masked pixels. Default: 0",
        default=0,
        type=float,
        action=SM,
    )
    opts.add_argument(
        "-o", "--output-dir",
        help="Output directory for masked TIFFs. Default: masked",
        default="masked",
        action=SM,
    )
    opts.add_argument(
        "--suffix",
        help="Suffix added before .tif. Default: _masked",
        default="_masked",
        action=SM,
    )
    opts.add_argument(
        "--overwrite",
        help="Overwrite existing outputs. Default: False",
        action="store_true",
        default=False,
    )
    opts.add_argument(
        "-d", "--dilate",
        help="Number of binary dilation iterations applied to the label mask. Default: 0",
        default=0,
        type=int,
        action=SM,
    )

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity.", action="store_true", default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    tif_files = match_files(args.input)
    seg_files = match_files(args.seg)

    if args.verbose:
        print(f"Input files: {[Path(f).name for f in tif_files]}")
        print(f"Seg files: {[Path(f).name for f in seg_files]}")

    if len(tif_files) != len(seg_files):
        raise ValueError(
            f"Number of input files must match number of segmentation files. "
            f"Inputs: {len(tif_files)}, Segs: {len(seg_files)}"
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for tif_file, seg_file in zip(tif_files, seg_files):
        tif_file = Path(tif_file)
        seg_file = Path(seg_file)

        print(f"\nProcessing image: {tif_file.name}")
        print(f"Using segmentation: {seg_file.name}")

        img = load_single_tif(tif_file)
        seg = load_single_tif(seg_file)

        if img.shape != seg.shape:
            raise ValueError(
                f"Image and segmentation shapes do not match:\n"
                f"  {tif_file.name}: {img.shape}\n"
                f"  {seg_file.name}: {seg.shape}"
            )

        if args.verbose:
            print(f"Unique segmentation values: {np.unique(seg)}")

        mask = seg == args.label

        if args.dilate > 0:
            mask = binary_dilation(mask, iterations=args.dilate)

            if args.verbose:
                print(
                    f"Dilated mask {args.dilate} iteration(s). "
                    f"Masked pixels: {mask.sum()}"
                )

        if not mask.any():
            raise ValueError(
                f"No pixels with label {args.label} were found in segmentation: {seg_file.name}"
            )

        masked_img = img.copy()
        masked_img[mask] = args.target_intensity

        output_path = output_dir / f"{tif_file.stem}{args.suffix}{tif_file.suffix}"

        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {output_path}. Use --overwrite to replace it.")

        tifffile.imwrite(output_path, masked_img)
        print(f"Saved: {output_path}")

    print("\nDone.\n")


if __name__ == "__main__":
    main()