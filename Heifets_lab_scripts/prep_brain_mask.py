#!/usr/bin/env python3

import argparse
import shutil
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_img_io import resolve_path
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples

def parse_args():
    parser = argparse.ArgumentParser(description='Copies a subset of autofluo tifs to a new dir for training ilastik to segment brains', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='reg_inputs/autofl_50um_tifs (from prep_reg.py)', default="reg_inputs/autofl_50um_tifs", action=SM)
    parser.add_argument('-o', '--output', help='path/dir to copy TIF files. Default: ilastik_brain_mask', default="ilastik_brain_mask", action=SM)
    parser.add_argument('-ss', '--slice_start', help='Number of the first slice to copy', default=10, type=int, action=SM)
    parser.add_argument('-si', '--slice_interval', help='Interval of slices to copy. Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Run script from the experiment directory w/ sample?? folder(s)
or run from a sample?? folder.

This script can be used to copy tifs for training ilastik to segment brains if --mask_dir <path/mask_dir> and -e <exp dirs> were not specified in prep_reg.py 

Example usage:     prep_brain_mask.py -e <list of experiment directories>"""
    return parser.parse_args()


def copy_specific_slices(sample_path, source_dir, target_dir, slice_start=10, slice_interval=50):

    # Determine which slices to copy
    tif_files = list(source_dir.glob('*.tif'))
    slice_numbers = range(slice_start, len(tif_files), slice_interval) # Start, stop, step

    # Copy the selected slices to the target directory
    for slice_number in slice_numbers:
        src_file_name = f'slice_{slice_number:04}.tif'  # Ensures four-digit formatting
        src_file = source_dir / src_file_name
        if src_file.exists():
            dest_file = target_dir / f'{sample_path.name}_slice_{slice_number}.tif'
            shutil.copy(src_file, dest_file)
            if args.verbose:
                print(f"Copied {src_file} to {dest_file}")
        else:
            print(f"File {src_file} does not exist and was not copied.")


def main():

    # Create the target directory for copying the selected slices
    target_dir = Path(args.output)
    target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define input paths
            source_path = resolve_path(sample_path, args.input)

            # Copy the selected slices to the target directory
            copy_specific_slices(sample_path, source_path, target_dir, slice_start=args.slice_start, slice_interval=args.slice_interval)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()