#!/usr/bin/env python3

"""
Use ``reg_affine_initializer_check`` (``raic``) from UNRAVEL to check if the initially aligned template is fully within the padded region of the fixed image.

Prerequisites:
    - ``affine_initializer`` or ``reg`` must have been run to generate the initially aligned template image.

Notes:
    - Registration is less accurate if the initially aligned template is not fully within the padded region of the fixed image.
    - This script checks the number of surface voxels in the initially aligned template that are above a specified threshold. 
    - If this number is greater than the threshold, it indicates that the initially aligned template may not be fully within the padded region of the fixed image.
    - This can be fixed by increasing the padding percentage (-pad) when running `reg`.

Usage:
------
    reg_affine_initializer_check -i <template__initial_alignment_to_fixed_img.nii.gz> [-t <threshold>] [-d list of paths] [-p sample??] [-v]
"""

from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.img_io import load_nii
from unravel.core.utils import get_pad_percent, log_command, print_func_name_args_times, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='<template>_initial_alignment_to_fixed_img.nii.gz name from `reg` that is in sample??/reg_outputs/', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-t', '--threshold', help='Voxel intensity threshold for checking if the initially aligned template is within the padded region of the fixed image. Default: 0', type=float, default=0, action=SM)
    opts.add_argument('-msv', '--max_surface_voxels', help='Max allowed surface voxels above intensity threshold. Default: 0', type=int, default=0)
    opts.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from ``reg`` (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Percentage of padding to add to each dimension of the fixed image (gives space for initial alignment of the moving image). Default: 0.25 (25%%).', default=0.25, type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@print_func_name_args_times()
def affine_initializer_check(nii_path, thres=0):
    """
    Check if the initially aligned template is fully within the padded region of the fixed image.

    Parameters:
    -----------
    nii_path : str or Path
        Path to the NIfTI file containing the initially aligned template image.
    thres : float, optional
        Voxel intensity threshold for checking if the initially aligned template is within the padded region of the fixed image. Default is 0.
    
    Returns:
    --------
    int
        The number of surface voxels in the initially aligned template that are above the specified threshold.
    """
    img = load_nii(nii_path)
    above_thresh_surface_voxel_count = (
        (img[0, :, :] > thres).sum() + 
        (img[-1, :, :] > thres).sum() + 
        (img[:, 0, :] > thres).sum() + 
        (img[:, -1, :] > thres).sum() + 
        (img[:, :, 0] > thres).sum() + 
        (img[:, :, -1] > thres).sum()
    )
    return above_thresh_surface_voxel_count

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            img_path = sample_path / args.reg_outputs / args.input

            above_thresh_surface_voxel_count = affine_initializer_check(img_path, args.threshold)

            if above_thresh_surface_voxel_count > args.max_surface_voxels:
                print(f"\n[yellow]WARNING: {Path(sample_path.name, args.reg_outputs, args.input)} has {above_thresh_surface_voxel_count} surface voxels above threshold{args.threshold }. This may indicate that the initially aligned template is not fully within the padded region of the fixed image, which can affect registration, pulling atlas regions outwards where the initially aligned template goes out of view. Please check the initially aligned template image (e.g., in FSLeyes).")
                pad_percent = get_pad_percent(sample_path / args.reg_outputs, args.pad_percent)
                print(f"[yellow]Consider increasing the padding percentage {pad_percent} when running `reg` to ensure the initially aligned template is fully within the padded region of the fixed image.\n")

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()