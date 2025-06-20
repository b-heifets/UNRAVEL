#!/usr/bin/env python3

"""
Use ``reg_check`` (``rc``) from UNRAVEL to check registration QC, copies autofl_`*`um_masked_fixed_reg_input.nii.gz and atlas_in_tissue_space.nii.gz for each sample to a target dir.

Note:
    - This copies main outputs from ``reg`` to a target directory (reg_check by default) for further viewing.
    - Optional: To check for overmasking, this also pads the unmasked autofluo image and saves it to reg_outputs, so it can be copied to the target directory.

Next steps:
    - ``reg_check_fsleyes`` to visualize the registration outputs with an atlas overlay in FSLeyes.

Usage:
------
    reg_check [-td <path/target_output_dir>] [-ro reg_outputs] [-fri fixed_reg_in] [-wa warped_atlas] [-og] [-af autofl_img] [-pad pad_percent] [-d list of paths] [-p sample??] [-v]
"""

from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.img_io import load_nii, save_as_nii
from unravel.core.img_tools import pad
from unravel.core.utils import get_pad_percent, log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, copy_files


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-td', '--target_dir', help='path/target_output_dir name  for aggregating outputs from all samples. Default: reg_check', default='reg_check', action=SM)
    opts.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from ``reg``. Default: reg_outputs", default="reg_outputs", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Fixed image from registration ``reg``. Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-wa', '--warped_atlas', help='Warped atlas image from ``reg``. Default: atlas_CCFv3_2020_30um_in_tissue_space.nii.gz', default="atlas_CCFv3_2020_30um_in_tissue_space.nii.gz", action=SM)

    opts = parser.add_argument_group('Optional arguments for checking the unmasked autofluo image')
    opts.add_argument('-og', '--orig_autofl_img', help='Also copy the unmasked autofluo image to the target dir (to check for overmasking). Default: False', action='store_true', default=False)
    opts.add_argument('-af', '--autofl_img', help='Path to unmasked autofluorescence image from ``reg_prep`` (relative to sample dir). Default: reg_inputs/autofl_50um.nii.gz', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Padding percentage from ``reg``. Default: from parameters/pad_percent.txt or 0.15.', type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Create the target directory for copying the selected slices
    target_dir = Path(args.target_dir)
    target_dir.mkdir(exist_ok=True, parents=True)

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            # Define input paths
            source_path = sample_path / args.reg_outputs

            # Copy the selected slices to the target directory
            copy_files(source_path, target_dir, args.fixed_reg_in, sample_path, args.verbose)
            copy_files(source_path, target_dir, args.warped_atlas, sample_path, args.verbose)

            # Copy the original autofluo image if specified
            if args.orig_autofl_img:
                autofl_nii_pad_path = source_path / Path(args.autofl_img).name
                if not autofl_nii_pad_path.exists():
                    autofl_path = sample_path / args.autofl_img
                    pad_percent = get_pad_percent(sample_path / args.reg_outputs, args.pad_percent)

                    autofl_img = load_nii(autofl_path)
                    autofl_img_pad = pad(autofl_img, pad_percent=pad_percent)

                    # Save the padded autofluo image
                    ref_nii = sample_path / args.reg_outputs / args.fixed_reg_in
                    save_as_nii(autofl_img_pad, autofl_nii_pad_path, reference=ref_nii)

                # Copy the padded autofluo image to the target directory
                copy_files(source_path, target_dir, autofl_nii_pad_path.name, sample_path, args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()