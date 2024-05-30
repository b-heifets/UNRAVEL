#!/usr/bin/env python3

import argparse
import shutil
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.argparse_utils import SuppressMetavar, SM
from unravel.config import Configuration
from unravel.utils import print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Loads immunofluo image, subtracts background, and warps to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_dir name for gathering files. Default: current working dir', default=None, action=SM)
    parser.add_argument('-i', '--input', help='relative path to the source file to copy (if sample?? )', required=True, action=SM)
    parser.add_argument('-a', '--add_prefix', help='Add "sample??_" prefix to the output files', action='store_true')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Usage:    aggregate_files.py -i atlas_space/sample??_FOS_rb4_gubra_space_z_LRavg.nii.gz -v -e $DIRS"""
    return parser.parse_args()


def aggregate_files_from_sample_dirs(sample_path, pattern, rel_path_to_src_file, target_dir, add_prefix=False, verbose=False):
    if f"{pattern}_" in rel_path_to_src_file:
        src_path = sample_path / rel_path_to_src_file.replace(f"{pattern}_", f"{sample_path.name}_")
    else:
        src_path = sample_path / rel_path_to_src_file

    if add_prefix: 
        target_output = target_dir / f"{sample_path.name}_{src_path.name}"
        if verbose and src_path.exists():
            print(f"Copying {src_path.name} as {target_output.name}")
    else:
        target_output = target_dir / src_path.name
        if verbose and src_path.exists():
            print(f"Copying {src_path}")
    if src_path.exists():
        shutil.copy(src_path, target_output)


def main():
    if args.target_dir is None:
        target_dir = Path().cwd()
    else: 
        target_dir = Path(args.target_dir)
        target_dir.mkdir(exist_ok=True, parents=True)

    if args.verbose: 
        print(f'\nCopying files to: {target_dir}\n')

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            aggregate_files_from_sample_dirs(sample_path, args.pattern, args.input, target_dir, args.add_prefix, args.verbose)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()