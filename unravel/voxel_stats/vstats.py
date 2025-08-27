#!/usr/bin/env python3

"""
Use ``vstats`` (``vs``) from UNRAVEL to run voxel-wise stats using FSL's randomise_parallel command.

Prereqs: 
    - Input images from ``vstats_prep``, ``vstats_z_score``, or ``vstats_whole_to_avg``.

Inputs:
    - `*`.nii.gz files in the current directory with conditions as prefixes (e.g., saline_1.nii.gz, saline_2.nii.gz, drug_1.nii.gz, drug_2.nii.gz)

Outputs:
    - stats/ directory with randomise_parallel outputs (e.g., uncorrected 1-p value maps [vox_p]).
    - The name of the current directory is used as the prefix for the output files.

Next commands:
    - Run ``cstats_fdr_range`` and ``cstats_fdr`` to correct for multiple comparisons.

Note:
    - 1 minus p (1-p) value maps are made for visualization (e.g., in FSLeyes), so use 0.95 as the uncorrect threshold for alpha = 0.05.
    - The --options flag is used to pass additional options to the randomise command.
    - It should be the last flag specified in the command.
    - The options should be specified as separate strings, e.g., --options --seed=1 -T
    - For info on how to set up and run voxel-wise analyses, see: https://b-heifets.github.io/UNRAVEL/guide.html#voxel-wise-stats
    - For a t-test design, tstat1 is group1 > group2 and tstat2 is group2 > group1 (conditions are sorted alphabetically)
    - For an ANOVA design, fstat1 is the first contrast, fstat2 is the second contrast, and so on (these are 1-p value maps are non-directional)

Usage:
------
    vstats [-mas mask.nii.gz] [-p 18000] [--kernel 0] [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-v] [--options --seed=1]
"""

import argparse
import shutil
import subprocess
import sys
from fsl.wrappers import fslmaths, avwutils
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--mask', help='path/mask.nii.gz', action=SM)
    opts.add_argument('-p', '--permutations', help='Number of permutations (divisible by 300). Default: 18000', type=int, default=18000, action=SM)
    opts.add_argument('-k', '--kernel', help='Smoothing kernel radius in mm if > 0. Default: 0 ', default=0, type=float, action=SM)
    opts.add_argument('-a', '--atlas', help='path/atlas.nii.gz (copied to stats/ for viewing; Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)
    opts.add_argument('-opt', '--options', help='Additional options for randomise, specified like "--seed=1 -T"', nargs=argparse.REMAINDER, default=[])

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', default=False, action='store_true')

    return parser.parse_args()

# TODO: Add an email option to send a message when the processing is complete. Add progress bar. See if fragments can be generated in parallel. Could make avg and avg diff maps in this script (e.g., before merge since this is fast)
# TODO: Test nargs=argparse.REMAINDER with options

def check_fdr_command():
    """Check if the 'fdr' command is available in the system's path."""
    if shutil.which('fdr') is None:
        print("Error: The 'fdr' command is not available. Please ensure that it is installed and in your PATH.")
        sys.exit(1)

def create_design_ttest2(mat_file, group1_size, group2_size):
    """Create design matrix for a two-group unpaired t-test."""
    cmd = ["design_ttest2", str(mat_file), str(group1_size), str(group2_size)]
    subprocess.run(cmd, check=True, stderr=subprocess.STDOUT)

def get_groups_info():
    groups = {}
    files = match_files('*.nii.gz')
    for file in files:
        prefix = file.stem.split('_')[0]
        if prefix in groups:
            groups[prefix] += 1
        else:
            groups[prefix] = 1

    for group, count in groups.items():
        print(f"    Group {group} has {count} members")

    return groups

def calculate_fragments(num_contrasts, total_permutations_per_contrast=18000, permutations_per_fragment=300):
    """Calculate the total number of fragments based on the number of contrasts."""
    if num_contrasts is None:
        return "Number of contrasts not determined."
    total_fragments = (total_permutations_per_contrast * num_contrasts) // permutations_per_fragment
    return total_fragments

@print_func_name_args_times()
def run_randomise_parallel(input_image_path, permutations, output_name, design_fts_path, mask_path=None, options=None, verbose=False):
    
    # Construct the base command
    command = [
        "randomise_parallel",
        "-i", str(input_image_path),
        "-n", str(permutations),
        "-o", str(output_name),
        "-d", "stats/design.mat",
        "-t", "stats/design.con",
        "--uncorrp",
        "-x"
    ]
    
    # Add the mask argument if provided
    if mask_path is not None:
        command.extend(["-m", str(mask_path)])

    # Append any additional options
    if options is not None:
        command.extend(options)  # Ensure options is a list of strings

    design_fts_path = str(design_fts_path) if Path(design_fts_path).exists() else None
    if design_fts_path:
        command += ["-f", design_fts_path]

    command_line = " ".join(command)
    print(f"\n[bold]{command_line}\n")

    if verbose is not None:
        # Execute the command and stream output
        try:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
                for line in proc.stdout:
                    print(line, end='')  # Print each line as it comes
            if proc.returncode != 0:
                print("Error executing command.")
        except Exception as e:
            print(f"Error during command execution: {str(e)}")
    else:
        # Execute the command silently and capture output
        try:
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            if process.returncode == 0:
                print("randomise_parallel executed successfully\n")
            else:
                print("Error executing randomise_parallel:\n" + process.stderr)
        except subprocess.CalledProcessError as e:
            print("Error during command execution:\n" + str(e))


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    cwd = Path.cwd()
    stats_dir = cwd / 'stats'
    stats_dir.mkdir(exist_ok=True)

    # Copy the mask and the atlas to the stats directory using shutil
    if args.mask and Path(args.mask).exists():
        shutil.copy(args.mask, stats_dir)
    elif args.mask and not Path(args.mask).exists():
        print(f"\n    [yellow]{args.mask} does not exist. Please provide a valid mask file. Skipping masking and copying to stats/\n")

    if Path(args.atlas).exists():
        shutil.copy(args.atlas, stats_dir)
    else:
        print(f"\n    [yellow]{args.atlas} does not exist. Skipping copying to stats/\n")


    # Merge and smooth the input images
    images = match_files('*.nii.gz')
    merged_file = stats_dir / 'all.nii.gz'
    if not merged_file.exists():
        print('\n    Merging *.nii.gz into ./stats/all.nii.gz with this order of files:')
        for image in images:
            print(f'    {image}')
        avwutils.fslmerge('t', str(merged_file), *images)
    else: 
        print('\n    ./stats/all.nii.gz exists. Skipping...\n')
 
    # Smooth the image with a kernel
    if args.kernel > 0:
        kernel_in_um = int(args.kernel * 1000)
        smoothed_file = merged_file.with_name(f'all_s{kernel_in_um}.nii.gz')
        print(f'\n    Smoothing all.nii.gz w/ fslmaths stats/all -s {args.kernel} {smoothed_file}')
        fslmaths(merged_file).s(args.kernel).run(output=smoothed_file)
        glm_input_file = smoothed_file
    else:
        glm_input_file = merged_file

    # Set up required design files or check that they exist
    groups_info = get_groups_info()
    group_keys = list(groups_info.keys())
    design_fts_path = stats_dir / 'design.fts'
    if len(group_keys) == 2:
        design_path_and_prefix = stats_dir / 'design'
        create_design_ttest2(design_path_and_prefix, groups_info[group_keys[0]], groups_info[group_keys[1]])
        print(f"\n    Running t-test for groups {group_keys[0]} and {group_keys[1]}\n")
    elif len(group_keys) > 2:
        print("\n    Running ANOVA\n")
        if not design_fts_path.exists():
            print(f'\n    [red1]{design_fts_path} does not exist. See extended help for setting up files for the ANOVA\n')
            import sys ; sys.exit() 
    else:
        print("\n    [red1]There should be at least two groups with different prefixes in the input .nii.gz files.\n")

    output_prefix = stats_dir / cwd.name

    # Run the randomise_parallel command
    run_randomise_parallel(glm_input_file, args.permutations, output_prefix, design_fts_path, args.mask, args.options, args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()