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
    parser = argparse.ArgumentParser(description='Copies a subset of .tif files to a new dir for training ilastik', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='reg_inputs/autofl_50um_tifs (from prep_reg.py) or name of directory with raw tifs', default=None, action=SM)
    parser.add_argument('-o', '--output', help='path/dir to copy TIF files. Default: ilastik_brain_mask', default="ilastik_brain_mask", action=SM)
    parser.add_argument('-s', '--slices', help='List of slice numbers to copy, e.g., 0000 0400 0800', nargs='*', type=str, default=[])
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Run script from the experiment directory w/ sample?? folder(s)
or run from a sample?? folder.

Purposes:
 - Copy tifs if --mask_dir <path/mask_dir> and -e <exp dirs> were not specified in prep_reg.py 
 - Copy tifs to segment full resolution immunofluorescence images.

Example usage:     copy_tifs.py -e <list of experiment directories>"""
    return parser.parse_args()


def copy_specific_slices(sample_path, source_dir, target_dir, slice_numbers):
    """Copy the specified slices to the target directory.
    
    Args:
        - sample_path (Path): Path to the sample directory.
        - source_dir (Path): Path to the source directory containing the .tif files.
        - target_dir (Path): Path to the target directory where the selected slices will be copied.
        - slice_numbers (list): List of slice numbers to copy."""
    
    for file_path in source_dir.glob('*.tif'):
        if any(file_path.stem.endswith(f"{slice:04}") for slice in map(int, slice_numbers)):
            dest_file = target_dir / f'{sample_path.name}_{file_path.name}'
            shutil.copy(file_path, dest_file)
            if args.verbose:
                print(f"Copied {file_path} to {dest_file}")
        else:
            if args.verbose:
                print(f"File {file_path.name} does not match specified slices and was not copied.")


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
            copy_specific_slices(sample_path, source_path, target_dir, args.slices)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()