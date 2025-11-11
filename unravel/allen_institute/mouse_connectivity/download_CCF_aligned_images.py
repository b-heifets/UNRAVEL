#!/usr/bin/env python3

"""
Use ``download_CCF_aligned_images.py`` from UNRAVEL to download connectivity images from the Allen Brain Atlas Mouse Connectivity API.

Notes:
    - https://allensdk.readthedocs.io/en/latest/connectivity.html
    - https://allensdk.readthedocs.io/en/stable/_static/examples/nb/mouse_connectivity.html
    - https://alleninstitute.github.io/AllenSDK/allensdk.api.queries.mouse_connectivity_api.html#allensdk.api.queries.mouse_connectivity_api.MouseConnectivityApi
    - Segmented files have been warped to CCFv3 with linear interpolation.
    
"""

from allensdk.api.queries.mouse_connectivity_api import MouseConnectivityApi
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Experiment ID(s) to download data for (e.g., 113144533)', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-r', '--resolution', help='Resolution for images in micrometers (10, 25, 50). Default: 25', type=int, default=25, choices=[10, 25, 50], action=SM)
    opts.add_argument('-o', '--output', help='Path to output dir for images. Default: connectivity', default='connectivity', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def download_connectivity_data(experiment_id: int, outdir: str = "connectivity", resolution: int = 25):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    mca = MouseConnectivityApi()

    # 1️⃣  Reference-aligned image channel volumes (25 µm)
    zip_path = Path(outdir) / f"{experiment_id}_{resolution}um_image_channels.zip"
    print(f"⬇️  Downloading reference-aligned RGB image channels → {zip_path}")
    mca.download_reference_aligned_image_channel_volumes(
        data_set_id=experiment_id,
        save_file_path=zip_path
    )

    # 2️⃣  Projection density volume (25 µm)
    proj_path = Path(outdir) / f"{experiment_id}_projection_density_{resolution}um.nrrd"
    print(f"⬇️  Downloading projection density volume → {proj_path}")
    mca.download_projection_density(str(proj_path), experiment_id, resolution)
    print(f"✅ Finished downloading experiment {experiment_id}")

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    output_dir = Path(args.output) if args.output else Path('connectivity')
    download_connectivity_data(args.input, output_dir, resolution=args.resolution)

    verbose_end_msg()

if __name__ == '__main__':
    main()
