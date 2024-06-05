#!/usr/bin/env python3

import argparse
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import print_cmd_and_times, initialize_progress_bar, get_samples, copy_files

def parse_args():
    parser = argparse.ArgumentParser(description='Copies a subset of .tif files to a new dir for training ilastik', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_output_dir name for aggregating outputs from all samples (cwd if omitted).', default=None, action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from reg.py. Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Fixed image from registration (reg.py). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-wa', '--warped_atlas', help='Warped atlas image from reg.py. Default: gubra_ano_combined_25um_in_tissue_space.nii.gz', default="gubra_ano_combined_25um_in_tissue_space.nii.gz", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Usage: 
check_reg.py -e <list of experiment directories> # copies to the current working directory
check_reg.py -e <list of experiment directories> -td <target_output_dir"""
    return parser.parse_args()


def main():
    args = parse_args()

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
            source_path = sample_path / args.reg_outputs

            # Copy the selected slices to the target directory
            copy_files(source_path, target_dir, args.fixed_reg_in, sample_path, args.verbose)
            copy_files(source_path, target_dir, args.warped_atlas, sample_path, args.verbose)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
