#!/usr/bin/env python3

"""
Use ``download_and_convert_CCF_aligned_images.py`` from UNRAVEL to download connectivity images from the Allen Brain Atlas Mouse Connectivity API and convert them to NIfTI format.

Usage:
------
    `download_and_convert_CCF_aligned_images.py -i 113144533 [-r reference.nii.gz] [-o output_dir/] [-res 25] [-v]`
"""

import zipfile
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.allen_institute.mouse_connectivity.download_CCF_aligned_images import download_connectivity_data
from unravel.allen_institute.mouse_connectivity.nrrd_to_nii import nrrd_to_nii
from unravel.allen_institute.mouse_connectivity.raw_to_nii import raw_to_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, match_files, print_func_name_args_times, resolve_output_paths, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--id', help='Experiment ID(s) to download data for (e.g., 113144533)', required=True, nargs='*', type=int, action=SM)
    reqs.add_argument('-r', '--ref_nii', help='Path to reference .nii.gz for header and affine info (must match downloaded images).', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-res', '--resolution', help='Resolution for images in micrometers (10, 25, 50). Default: 25', type=int, default=25, choices=[10, 25, 50], action=SM)
    opts.add_argument('-o', '--output', help='Path to output dir for images. Default: connectivity/<id>_<resolution>um', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@print_func_name_args_times()
def download_and_convert_connectivity_data(exp_ids: list[int], resolution: int = 25, ref_nii: str | Path = None, output_dir: str | Path = None):
    """Download and convert connectivity data for given experiment IDs."""
    for exp_id in exp_ids:
        print(f"\n[bold green]Downloading connectivity data for experiment ID: {exp_id}[/bold green]\n")
        output_dir = Path(output_dir) if output_dir else Path('connectivity') / f"{exp_id}_{resolution}um"

        download_connectivity_data(exp_id, output_dir, resolution=resolution)

        # Output structure (3 channels: red, green, blue + a .nrrd segmentation file):
        # {output_dir}/{exp_id}_25um_image_channels.zip with: resampled_blue.raw, resampled_blue.mhd, etc.
        # {output_dir}/{exp_id}_projection_density_25um.nrrd

        # Extract and convert .raw files to .nii.gz
        zip_path = output_dir / f"{exp_id}_{resolution}um_image_channels.zip"
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        raw_pattern = str(output_dir / "*.raw")
        raw_paths = match_files(raw_pattern)
        raw_output_paths = resolve_output_paths(file_paths=raw_paths, ext=".nii.gz")
        for raw_path, output_path in zip(raw_paths, raw_output_paths):
            raw_to_nii(raw_path, output_path, ref_nii_path=ref_nii, dtype='uint16')
    
        # Convert .nrrd segmentation file to .nii.gz
        nrrd_path = output_dir / "*.nrrd"
        nrrd_paths = match_files(str(nrrd_path))
        nrrd_output_paths = resolve_output_paths(file_paths=nrrd_paths, ext=".nii.gz")
        for in_path, out_path in zip(nrrd_paths, nrrd_output_paths):
            nrrd_to_nii(in_path, out_path, ref_nii_path=ref_nii, dtype='float32')

        # Clean up ".mhd", ".raw", ".zip", ".nrrd" files after conversion
        for file_path in output_dir.glob("*"):
            if file_path.suffix in ['.mhd', '.raw', '.zip', '.nrrd']:
                file_path.unlink()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    download_and_convert_connectivity_data(exp_ids=args.id, resolution=args.resolution, ref_nii=args.ref_nii, output_dir=args.output)

    verbose_end_msg()

if __name__ == '__main__':
    main()
