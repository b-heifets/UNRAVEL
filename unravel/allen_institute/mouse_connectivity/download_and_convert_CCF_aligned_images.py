#!/usr/bin/env python3

"""
Use ``download_and_convert_CCF_aligned_images.py`` from UNRAVEL to download/convert CCF-aligned images from the Allen Brain Atlas Mouse Connectivity API.

Outputs:
    - Output dir: connectivity/<id>
    - Reference-aligned images: resampled_<red|green|blue>.nii.gz
    - <id>_projection_density_25um.nii.gz
    - <id>_projection_density_10um.nii.gz (if downloaded)

Usage:
------
    `download_and_convert_CCF_aligned_images.py -i 113144533 [-r 25um_reference.nii.gz] [-r10 10um_reference.nii.gz] [-v]`
"""

import zipfile
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.allen_institute.mouse_connectivity.download_CCF_aligned_images import download_CCF_aligned_10um_projection_density, download_CCF_aligned_connectivity_data
from unravel.allen_institute.mouse_connectivity.nrrd_to_nii import nrrd_to_nii
from unravel.allen_institute.mouse_connectivity.raw_to_nii import raw_to_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, match_files, print_func_name_args_times, resolve_output_paths, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--id', help='Experiment ID(s) to download data for (e.g., 113144533)', required=True, nargs='*', type=int, action=SM)
    reqs.add_argument('-r', '--ref_nii', help='Path to 25 µm reference .nii.gz for header and affine info.', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-r10', '--ref_nii_10um', help='Path to 10 µm reference .nii.gz to optionally download 10 µm projection density images.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@print_func_name_args_times()
def download_and_convert_connectivity_data(exp_ids: list[int], ref_nii: str | Path = None, ref_nii_10um: str | Path = None):
    """Download and convert connectivity data for given experiment IDs."""
    for exp_id in exp_ids:
        print(f"\n[bold green]Downloading connectivity data for experiment ID: {exp_id}[/bold green]\n")
        exp_dir = Path().cwd() / str(exp_id)

        download_CCF_aligned_connectivity_data(exp_id, exp_dir)
        # Output structure (3 channels: red, green, blue + a .nrrd segmentation file):
        # {output_dir}/{exp_id}_25um_image_channels.zip with: resampled_blue.raw, resampled_blue.mhd, etc.
        # {output_dir}/{exp_id}_projection_density_25um.nrrd

        if ref_nii_10um:
            download_CCF_aligned_10um_projection_density(exp_id, exp_dir)
            # {output_dir}/{exp_id}_projection_density_10um.nrrd

        # Extract and convert .raw files to .nii.gz
        zip_path = exp_dir / f"{exp_id}_25um_image_channels.zip"
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(exp_dir)
        raw_pattern = str(exp_dir / "*.raw")
        raw_paths = match_files(raw_pattern)
        raw_output_paths = resolve_output_paths(file_paths=raw_paths, ext=".nii.gz")
        for raw_path, output_path in zip(raw_paths, raw_output_paths):
            raw_to_nii(raw_path, output_path, ref_nii_path=ref_nii, dtype='uint16')

        # Rename resampled_blue.nii.gz --> f"{exp_id}_resampled_blue.nii.gz", etc.
        print()
        for nii_path in exp_dir.glob("resampled_*.nii.gz"):
            new_name = f"{exp_id}_{nii_path.name}"
            nii_path.rename(exp_dir / new_name)
            print(f"    Renamed {nii_path.name} --> {new_name}")

        # Convert .nrrd segmentation file to .nii.gz
        nrrd_path = exp_dir / f"{exp_id}_projection_density_25um.nrrd"
        nrrd_paths = match_files(str(nrrd_path))
        nrrd_output_paths = resolve_output_paths(file_paths=nrrd_paths, ext=".nii.gz")
        for in_path, out_path in zip(nrrd_paths, nrrd_output_paths):
            nrrd_to_nii(in_path, out_path, ref_nii_path=ref_nii, dtype='float32')

        # Convert 10 µm projection density .nrrd to .nii.gz if downloaded
        if ref_nii_10um:
            nrrd_10um_path = exp_dir / f"{exp_id}_projection_density_10um.nrrd"
            nrrd_10um_paths = match_files(str(nrrd_10um_path))
            nrrd_10um_output_paths = resolve_output_paths(file_paths=nrrd_10um_paths, ext=".nii.gz")
            for in_path, out_path in zip(nrrd_10um_paths, nrrd_10um_output_paths):
                nrrd_to_nii(in_path, out_path, ref_nii_path=ref_nii_10um, dtype='float32')

        # Clean up ".mhd", ".raw", ".zip", ".nrrd" files after conversion
        for file_path in exp_dir.glob("*"):
            if file_path.suffix in ['.mhd', '.raw', '.zip', '.nrrd']:
                file_path.unlink()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    download_and_convert_connectivity_data(exp_ids=args.id, ref_nii=args.ref_nii, ref_nii_10um=args.ref_nii_10um)
    
    verbose_end_msg()

if __name__ == '__main__':
    main()
