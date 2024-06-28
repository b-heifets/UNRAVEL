#!/usr/bin/env python3

"""
Use ``reg_check`` from UNRAVEL to check registration QC, copies autofl_<asterisk>um_masked_fixed_reg_input.nii.gz and atlas_in_tissue_space.nii.gz for each sample to a target dir.

Usage:
------
    reg_check -e <list of experiment directories> # copies to the current working directory
    reg_check -e <list of experiment directories> -td <target_output_dir
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
    parser.add_argument('-td', '--target_dir', help='path/target_output_dir name for aggregating outputs from all samples (cwd if omitted).', default=None, action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from ``reg``. Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Fixed image from registration ``reg``. Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-wa', '--warped_atlas', help='Warped atlas image from ``reg``. Default: gubra_ano_combined_25um_in_tissue_space.nii.gz', default="gubra_ano_combined_25um_in_tissue_space.nii.gz", action=SM)
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
            source_path = sample_path / args.reg_outputs

            # Copy the selected slices to the target directory
            copy_files(source_path, target_dir, args.fixed_reg_in, sample_path, args.verbose)
            copy_files(source_path, target_dir, args.warped_atlas, sample_path, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()