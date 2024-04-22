#!/usr/bin/env python3

import argparse
import shutil
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples


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

            if f"{args.pattern}_" in args.input:
                input_path = sample_path / args.input.replace(f"{args.pattern}_", f"{sample_path.name}_")
            else:
                input_path = sample_path / args.input

            if args.add_prefix: 
                target_output = target_dir / f"{sample_path.name}_{input_path.name}"
                if args.verbose and input_path.exists():
                    print(f"Copying {input_path.name} as {target_output.name}")
            else:
                target_output = target_dir / input_path.name
                if args.verbose and input_path.exists():
                    print(f"Copying {input_path}")
            if input_path.exists():
                shutil.copy(input_path, target_output)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()