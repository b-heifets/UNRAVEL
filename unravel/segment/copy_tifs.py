#!/usr/bin/env python3

"""
Use ``seg_copy_tifs`` from UNRAVEL to copy a subset of .tif files to a target dir for training ilastik.

Usage to prep for ``seg_brain_mask``:
-------------------------------------
    seg_copy_tifs -i reg_inputs/autofl_50um_tifs -s 0000 0005 0050 -o ilastik_brain_mask

Usage to prep for ``seg_ilastik`` to segment full resolution immunofluorescence images:
---------------------------------------------------------------------------------------
    seg_copy_tifs -i raw_tif_dir -s 0100 0500 1000 -o ilastik_segmentation
"""

import argparse
import shutil
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.img_io import resolve_path
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='reg_inputs/autofl_50um_tifs (from ``reg_prep``) or name of directory with raw tifs', default=None, action=SM)
    parser.add_argument('-o', '--output', help='path/dir to copy TIF files. (e.g., ilastik_brain_mask or ilastik_segmentation)', required=True, action=SM)
    parser.add_argument('-s', '--slices', help='List of slice numbers to copy (4 digits each; space separated)', nargs='*', type=str, default=[])
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def copy_specific_slices(sample_path, source_dir, target_dir, slice_numbers, verbose=False):
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
            if verbose:
                print(f"Copied {file_path} to {dest_file}")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

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
            copy_specific_slices(sample_path, source_path, target_dir, args.slices, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()