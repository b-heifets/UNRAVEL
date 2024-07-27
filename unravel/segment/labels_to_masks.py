#!/usr/bin/env python3

"""
Use save_labels_as_masks.py from UNRAVEL to convert an ilastik segmentation tif series or other image labels to binary .nii.gz masks.

Usage:
------
    save_labels_as_masks.py -t seg_ilastik_1/IlastikSegmentation -o Ai14_seg_ilasik_1 -v

"""

import argparse
import nibabel as nib
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, print_func_name_args_times, initialize_progress_bar


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='rel_path/image (can be glob pattern [e.g., to tif dir or 1st tif])', required=True, action=SM)
    parser.add_argument('-o', '--output', help='NIfTI output file name (no extension)', required=True, action=SM)
    parser.add_argument('-l', '--labels', help='List of segmetation label IDs to save as binary .nii.gz images. Default: 1', default=1, nargs='+', type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def save_labels_as_masks(ndarray, label, segmentation_dir, output_name):
    """Converts label in an image to a binary mask and saves it as a .nii.gz file. Assumes < 256 labels."""
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

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            img_path = next(sample_path.glob(str(args.input)), None)
            if img_path is None:
                print(f"No files match the pattern {args.input} in {sample_path}")
                continue
            seg_img = load_3D_img(img_path)
            
            # Convert each label to a binary mask and save as .nii.gz
            if isinstance(args.labels, int):
                labels = [args.labels]
            if len(labels) == 1:
                save_labels_as_masks(seg_img, int(labels[0]), img_path.parent, args.output)
            else: 
                for label in labels:
                    output_name = f"{args.output}_{int(label)}.nii.gz"
                    save_labels_as_masks(seg_img, int(label), img_path.parent, output_name)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()