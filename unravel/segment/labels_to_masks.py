#!/usr/bin/env python3

"""
Use ``seg_labels_as_masks`` (``sl2m``) from UNRAVEL to convert an ilastik segmentation tif series or other image labels to binary .nii.gz masks.

Usage:
------
    ``seg_labels_as_masks`` -i seg_ilastik_1/IlastikSegmentation -o Ai14_seg_ilasik_1 [-l 1 2 3] [-d dirs] [-p pattern] [-v]
"""

import nibabel as nib
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, print_func_name_args_times, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='rel_path/image (can be glob pattern [e.g., to tif dir or 1st tif])', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='NIfTI output file name (no extension)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-l', '--labels', help='List of segmetation label IDs to save as binary .nii.gz images. Default: 1', default=1, nargs='*', type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Consolidate save_labels_as_masks() here and the one from unravel/segment/ilastik_pixel_classification.py

@print_func_name_args_times()
def save_labels_as_masks(ndarray, label, segmentation_dir, output_name, verbose=False):
    """Converts label in an image to a binary mask and saves it as a .nii.gz file. Assumes < 256 labels."""
    if verbose:
        print(f"\n    Converting label {label} to mask and saving as .nii.gz in {segmentation_dir}\n")
    label_img = (ndarray == label).astype(np.uint8)
    nifti_img = nib.Nifti1Image(label_img, np.eye(4))
    nib.save(nifti_img, segmentation_dir.joinpath(f"{output_name}"))


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
            seg_img = load_3D_img(img_path, verbose=args.verbose)
            
            # Convert each label to a binary mask and save as .nii.gz
            if isinstance(args.labels, int):
                labels = [args.labels]
            if len(labels) == 1:
                save_labels_as_masks(seg_img, int(labels[0]), img_path.parent, args.output, verbose=args.verbose)
            else: 
                for label in labels:
                    output_name = f"{args.output}_{int(label)}.nii.gz"
                    save_labels_as_masks(seg_img, int(label), img_path.parent, output_name, verbose=args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()