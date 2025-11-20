#!/usr/bin/env python3

"""
Use ``download_and_convert_CCF_aligned_injection_density.py`` from UNRAVEL to download/convert CCF-aligned injection density images from the Allen Brain Atlas Mouse Connectivity API.

Outputs:
    - Output dir: cwd/<id>/<id>_injection_density_25um.nii.gz

Next Steps:
    - Use ``injection_stats_summary.py`` to compute injection statistics using the converted .nii.gz files

Usage:
------
    `download_and_convert_CCF_aligned_injection_density.py -i 113144533 [-r 25um_reference.nii.gz] [-v]`
"""

import zipfile
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.allen_institute.mouse_connectivity.download_CCF_aligned_images import download_CCF_aligned_injection_density
from unravel.allen_institute.mouse_connectivity.nrrd_to_nii import nrrd_to_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, match_files, print_func_name_args_times, resolve_output_paths, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--id', help='Experiment ID(s) to download data for (e.g., 113144533)', required=True, nargs='*', type=int, action=SM)
    reqs.add_argument('-r', '--ref_nii', help='Path to 25 µm reference .nii.gz for header and affine info.', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def download_and_convert_injection_density(exp_ids: list[int], ref_nii: str | Path = None):
    """Download and convert injection density data for given experiment IDs."""
    for exp_id in exp_ids:
        print(f"\n[bold green]Downloading injection density data for experiment ID: {exp_id}[/bold green]\n")
        exp_dir = Path().cwd() / str(exp_id)

        # {exp_dir}/{exp_id}_injection_density_25um.nrrd
        download_CCF_aligned_injection_density(exp_id, exp_dir)

        # Convert .nrrd segmentation file to .nii.gz
        nrrd_path = exp_dir / f"{exp_id}_injection_density_25um.nrrd"
        nrrd_paths = match_files(str(nrrd_path))
        nrrd_output_paths = resolve_output_paths(file_paths=nrrd_paths, ext=".nii.gz")
        for in_path, out_path in zip(nrrd_paths, nrrd_output_paths):
            nrrd_to_nii(in_path, out_path, ref_nii_path=ref_nii, dtype='float32')

        # Clean up ".nrrd" files after conversion
        for file_path in exp_dir.glob("*"):
            if file_path.suffix in ['.nrrd']:
                file_path.unlink()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    download_and_convert_injection_density(exp_ids=args.id, ref_nii=args.ref_nii)
    
    verbose_end_msg()

if __name__ == '__main__':
    main()
