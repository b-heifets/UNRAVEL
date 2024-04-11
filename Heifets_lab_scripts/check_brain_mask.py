#!/usr/bin/env python3

import argparse
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples, copy_files

def parse_args():
    parser = argparse.ArgumentParser(description='For masking QC, copies autofluo_50um.nii.gz and autofluo_50_masked.nii.gz for each sampled to a target dir', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_output_dir name for aggregating outputs from all samples.', required=True, action=SM)
    parser.add_argument('-i', '--input', help='Output path. Default: reg_inputs/autofl_50um.nii.gz', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Usage: 
check_brain_mask.py -e <list of experiment directories> # copies to the current working directory
check_brain_mask.py -e <list of experiment directories> -td <target_output_dir"""
    return parser.parse_args()


def main():

    # Create the target directory for copying the selected slices
    target_dir = Path(args.target_dir) if args.target_dir is not None else Path.cwd()
    target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define input paths
            source_path = sample_path / Path(args.input).parent

            # Copy the selected slices to the target directory
            copy_files(source_path, target_dir, Path(args.input).name, sample_path, args.verbose)
            copy_files(source_path, target_dir, str(Path(args.input).name).replace('.nii.gz', '_masked.nii.gz'), sample_path, args.verbose)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()