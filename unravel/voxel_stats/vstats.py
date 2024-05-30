#!/usr/bin/env python3

import argparse
import shutil
import subprocess
from glob import glob
import sys
from fsl.wrappers import fslmaths, avwutils
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.argparse_utils import SM, SuppressMetavar
from unravel.config import Configuration
from unravel.utils import print_cmd_and_times, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description="Run voxel-wise stats using FSL's randomise_parallel command", formatter_class=SuppressMetavar)
    parser.add_argument('-mas', '--mask', help='path/mask.nii.gz', required=True, action=SM)
    parser.add_argument('-p', '--permutations', help='Number of permutations (divisible by 300). Default: 18000', type=int, default=18000, action=SM)
    parser.add_argument('-k', '--kernel', help='Smoothing kernel radius in mm if > 0. Default: 0 ', default=0, type=float, action=SM)
    parser.add_argument('-opt', '--options', help='Additional options for randomise, specified like "--seed=1 -T"', nargs='*', default=[])
    parser.add_argument('-on', '--output_prefix', help='Prefix of output files. Default: current working dir name.', action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = """Usage:    vstats.py -mas mask.nii.gz -v

Prereqs: 
    - Input images from prep_vstats.py, z-score.py, or whole_to_LR_avg.py
    - FSL installed and the following added to .bashrc or .zshrc (or run in terminal):
export FSLDIR=/usr/local/fsl
export PATH=${FSLDIR}/bin:${PATH}
. ${FSLDIR}/etc/fslconf/fsl.sh
export FSLDIR PATH
    - Source the .bashrc or .zshrc file (e.g., source ~/.bashrc) or restart the terminal
    
Inputs: 
    - Make glm folder named succiently (e.g., glm_<EX>_rb<4>_z_<contrast> for t-test or anova_<EX>_rb<4>_z)
    - Add *.nii.gz prepended with the condition (e.g., drug_sample01_gubra_space_z.nii.gz)
        - Optional: use prepend_conditions.py to add the condition to the file names
        - The condition should be one word (e.g., drug, saline, etc.)
        - Group order is alphabetical (e.g., drug is group 1 and saline is group 2)
        - The input images should be in the working directory
        - View the images in fsleyes to ensure they are aligned and the sides are correct
    - With whole brains, left and right sides can be averaged with whole_to_LR_avg.py, then use a unilateral hemisphere mask.

If glm_folder/stats/design.fts exists, run ANOVA, else run t-test.

Outputs are in glm_folder/stats.

T-test outputs:
    - vox_p_tstat1.nii.gz: uncorrected p values for tstat1 (group 1 > group 2)
    - vox_p_tstat2.nii.gz: uncorrected p values for tstat2 (group 1 < group 2)

ANOVA outputs:
    - vox_p_fstat1.nii.gz: uncorrected p values for fstat1 (1st contrast, e.g., drug vs saline)
    - vox_p_fstat2.nii.gz: uncorrected p values for fstat2 (2nd contrast, e.g., context1 vs context2)
    - vox_p_fstat3.nii.gz: uncorrected p values for fstat3 (3rd contrast, e.g., interaction)

Example of preparing for a ANOVA: 
    - For a 2x2 ANOVA, before running this script make ./anova_<EX>_rb<4>_z/stats/design/
    - Open terminal from ./stats and run: fsl
    - Misc -> GLM Setup
    - GLM Setup window: 
        - Higher-level / non-timeseries design 
        - # inputs: <total # of samples> 
    - EVs tab in GLM window: 
        - # of main EVs: 4 
        - Name EVs (e.g., EV1 = group 1) 
        - Group should be 1 for all 
    - Make design matrix: 
        - Under EV1 enter 1 for each subject in group 1 (1 row/subject). EV2-4 are 0 for these rows 
        - Under EV2 enter 1 for each subject in group 2, starting w/ row after the last row for group 1  
        - Follow this pattern for EV3 and EV4 
    - Contrasts & F-tests tab in GLM window: 
        - Contrasts: 3 
            - C1: Main_effect_<e.g.,drug> 1 1 -1 -1 (e.g., EV1/2 are drug groups and EV3/4 are saline groups) 
            - C2: Main_effect_<e.g., context> 1 -1 1 -1 (e.g., EV1/3 were in context1 and EV2/4 were in context2 )
            - C3: Interaction 1 -1 -1 1 
        - F-tests: 3
            - F1: click upper left box 
            - F2: click middle box
            - F3: click lower right box
    - GLM Setup window: 
        - Save -> click design -> OK 
    - Run: vstats.py from anova folder 

Background: 
https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/GLM 
https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Randomise/UserGuide

Afterwards run fdr.py to correct for multiple comparisons.
"""
    return parser.parse_args()

# TODO: Add an email option to send a message when the processing is complete. Add progress bar. See if fragments can be generated in parallel. Could make avg and avg diff maps in this script (e.g., before merge since this is fast)

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
    files = sorted(Path('.').glob('*.nii.gz'))
    groups = {}

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
def run_randomise_parallel(input_image_path, mask_path, permutations, output_name, design_fts_path, options, verbose):
    
    # Construct the command
    command = [
        "randomise_parallel",
        "-i", str(input_image_path),
        "-m", str(mask_path),
        "-n", str(permutations),
        "-o", str(output_name),
        "-d", "stats/design.mat",
        "-t", "stats/design.con",
        "--uncorrp",
        "-x"
    ] + options # Make sure options is a list of strings

    design_fts_path = str(design_fts_path) if Path(design_fts_path).exists() else None
    if design_fts_path:
        command += ["-f", design_fts_path]

    command_line = " ".join(command)
    print(f"\n[bold]{command_line}\n")

    if verbose:
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


def main(): 

    cwd = Path.cwd()
    stats_dir = cwd / 'stats'
    stats_dir.mkdir(exist_ok=True)

    # Copy the mask and the atlas to the stats directory using shutil
    shutil.copy(args.mask, stats_dir)
    shutil.copy(args.atlas, stats_dir)

    # Merge and smooth the input images
    images = glob('*.nii.gz') 
    merged_file = stats_dir / 'all.nii.gz'
    if not merged_file.exists():
        print('\n    Merging *.nii.gz into ./stats/all.nii.gz')
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

    if args.output_prefix:
        output_prefix = stats_dir / args.output_prefix
    else:
        output_prefix = stats_dir / cwd.name

    # Run the randomise_parallel command
    run_randomise_parallel(glm_input_file, args.mask, args.permutations, output_prefix, design_fts_path, args.options, args.verbose)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()