#!/usr/bin/env python3

"""
Use ``utils_clean_tifs`` from UNRAVEL to clean directories w/ tif series.

Run command from the experiment directory w/ sample?? folder(s), a sample?? folder, or provide -e or -d arguments.

Usage:
------
    utils_clean_tifs -t <tif_folder_name> -m -v

Tif directory clean up involves:
    - Moving subdirectories to parent dir
    - Moving non-TIF files to parent dir
    - Replacing spaces in TIF file names

Assumes that the extension of the TIF files is .tif or .ome.tif.
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
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-t', '--tif_dirs', help='List of tif series dirs to check.', nargs='*', required=True, action=SM)
    parser.add_argument('-m', '--move', help='Enable moving of subdirs and non-TIF files to parent dir.', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def clean_tifs_dir(path_to_tif_dir, move, verbose):
    """Clean up a directory containing TIF files:  
        - Move subdirs to parent dir 
        - Move non-TIF files to parent dir. 
        - Replace spaces in TIF file names with underscores.
    
    Args:
        path_to_tif_dir (str): Path to the directory containing the TIF files.
        move (bool): Enable moving of subdirs and non-TIF files to parent dir.
        verbose (bool): Increase verbosity."""
    if verbose:
        print(f"\n\nProcessing directory: {path_to_tif_dir}\n")

    # Move subdirectories to parent directory
    for subdir in path_to_tif_dir.iterdir():
        if subdir.is_dir():
            if verbose:
                print(f"Found subdir: {subdir}")
            if move:
                new_dir_name = f"{path_to_tif_dir.name}_{subdir.name}".replace(' ', '_')
                target_dir = path_to_tif_dir.parent / new_dir_name
                if not target_dir.exists():
                    shutil.move(str(subdir), str(target_dir))
                    if verbose: 
                        print(f"Moved {subdir} to {target_dir}")
                else:
                    print(f"Skipping {subdir} because {target_dir} already exists/")

    # Move non-TIF files and replace spaces in filenames
    for file in path_to_tif_dir.iterdir():
        if file.is_file() and not file.suffix.lower() in ('.tif', '.ome.tif'):
            if verbose:
                print(f"Found non-TIF file: {file}")
            if move:
                new_location = path_to_tif_dir.parent / file.name
                if not new_location.exists():
                    shutil.move(str(file), str(new_location))
                    print(f"Moved {file} to {new_location}")
                else:
                    print(f"Skipping {file} because {new_location} already exists.")
        elif file.suffix.lower() == '.tif':
            new_file_name = file.name.replace(' ', '_')
            if new_file_name != file.name:
                new_file_path = file.with_name(new_file_name)
                file.rename(new_file_path)


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

            # Clean TIF directories
            tif_dirs = [sample_path / tif_dir for tif_dir in args.tif_dirs]            
            for tif_dir in tif_dirs:
                clean_tifs_dir(Path(tif_dir), args.move, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()