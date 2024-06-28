#!/usr/bin/env python3

"""
Use ``reg_check_brain_mask`` from UNRAVEL for masking QC, copies autofluo_50um.nii.gz and autofluo_50_masked.nii.gz for each sampled to a target dir

Usage:
------
    reg_check_brain_mask -e <list of experiment directories> # copies to the current working directory
    reg_check_brain_mask -e <list of experiment directories> -td <target_output_dir
"""

import argparse
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, copy_files

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_output_dir name for aggregating outputs from all samples. If omitted, uses cwd', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Output path. Default: reg_inputs/autofl_50um.nii.gz', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

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

    verbose_end_msg()
    

if __name__ == '__main__':
    main()