#!/usr/bin/env python3

"""
Use ``img_filter_objects_by_size`` or ``filter_objects`` from UNRAVEL to filter objects (e.g., cells) by size. 

Note: 
    - This assumes the input is already a binary image (use ``img_math`` to binarize if needed).

Usage:
------
    img_filter_objects_by_size -i rel_path/segmentation_image.nii.gz [-m 2] [-o rel_path/segmentation_image_minVoxels_2.nii.gz] [-c 6] [-inv] [-d list of paths] [-p sample??] [-v]
"""

import cc3d
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_nii, save_as_nii
from unravel.core.utils import get_stem, log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/segmentation_image.nii.gz (can be glob pattern)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-m', '--min_voxels', help='Minimum voxel count per connected component to keep (default: 1 keeps all)', type=int, default=1, action=SM)
    opts.add_argument('-o', '--output', help='rel_path/seg_img_out.nii.gz. Default: <args.input>_minVoxels_<min_voxels>.nii.gz', default=None, action=SM)
    opts.add_argument('-c', '--connectivity', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, action=SM)
    opts.add_argument('-inv', '--invert', help='Invert the filtering to keep small objects instead of large ones. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


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

            img_path = next(sample_path.glob(str(args.input)), None)
            if img_path is None:
                print(f"No files match the pattern {args.input} in {sample_path}")
                continue
            if not str(img_path).endswith('.nii.gz'):
                raise ValueError("Input file must be a .nii.gz file")
            
            if args.verbose:
                print(f"\nProcessing: {img_path}")

            # Define output
            if args.output is not None:
                output_path = sample_path / args.output
            else:
                output_path = Path(str(img_path).replace(".nii.gz", f"_minVoxels_{args.min_voxels}.nii.gz"))

            if output_path.exists():
                print(f"Output file {output_path} already exists. Skipping...")
                progress.update(task_id, advance=1)
                continue

            # Load the segmentation image
            seg_img = load_nii(img_path)

            filtered_img = cc3d.dust(
                seg_img,
                threshold=args.min_voxels,
                connectivity=args.connectivity,
                invert=args.invert, # keep small objects instead of large ones
                in_place=True, # If true, modify the input image directly (saves memory)
                binary_image=True,
            )

            # Save the filtered image            
            save_as_nii(filtered_img, output_path, data_type=np.uint8, reference=img_path)

            if args.verbose:
                print(f"    Saved filtered image to: {output_path}\n")

            progress.update(task_id, advance=1)
    
    verbose_end_msg()
    

if __name__ == '__main__':
    main()