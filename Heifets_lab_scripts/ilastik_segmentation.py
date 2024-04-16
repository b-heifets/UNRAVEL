#!/usr/bin/env python3

import argparse
import nibabel as nib
from pathlib import Path
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_3D_img
from unravel_img_tools import ilastik_segmentation
from unravel_utils import get_samples, initialize_progress_bar, print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description="Run Ilastik's pixel classification workflow on a tif series", formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-ilp', '--ilastik_prj', help='path/ilastik_project.ilp', required=True, action=SM)
    parser.add_argument('-i', '--input', help='path/input_dir_w_tifs', required=True, action=SM)
    parser.add_argument('-o', '--output', help='output dir name', default=None, action=SM)
    parser.add_argument('-l', '--labels', help='List of labels to save as binary .nii.gz images', nargs='+', type=int, default=None, action=SM)
    parser.add_argument('-rm', '--rm_tifs', help='Delete the dir w/ tifs', action='store_true', default=False)
    parser.add_argument('-log', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Usage:    ilastik_segmentation.py -i cfos -o cfos_seg -ilp path/ilastik_project.ilp

This script is for pixel classification. 
"""
    return parser.parse_args()


@print_func_name_args_times()
def save_labels_as_masks(tif_dir, labels, segmentation_dir, output_name):
    img = load_3D_img(tif_dir) 
    for label in labels:
        print(f"\n    Converting label {label} to mask and saving as .nii.gz in {segmentation_dir}\n")
        label_img = (img == label).astype(np.uint8)
        nifti_img = nib.Nifti1Image(label_img, np.eye(4))
        nib.save(nifti_img, segmentation_dir.joinpath(f"{output_name}_{label}.nii.gz"))


def main():
    args = parse_args()

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define output
            segmentation_dir = sample_path / args.output
            tif_dir = segmentation_dir / args.output
            if args.labels: 
                last_label = args.labels[-1]
                final_output = segmentation_dir.joinpath(f"{args.output}_{last_label}.nii.gz")
            else: 
                final_output = tif_dir
            if final_output.exists():
                print(f"\n\n    {final_output.name} already exists. Skipping.\n")
                continue

            if not tif_dir.exists(): 
                # Perform pixel classification and output segmented tifs to output dir
                tif_dir.mkdir(exist_ok=True, parents=True)
                ilastik_segmentation(args.input, args.ilastik_prj, tif_dir, ilastik_log=args.ilastik_log)

            # Convert each label to a binary mask and save as .nii.gz
            if args.labels:
                save_labels_as_masks(tif_dir, args.labels, segmentation_dir, args.output)

            if args.rm_tifs: 
                Path(tif_dir).unlink()

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()