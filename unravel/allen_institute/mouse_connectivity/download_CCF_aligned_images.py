#!/usr/bin/env python3

"""
Use ``download_CCF_aligned_images.py`` from UNRAVEL to download connectivity images from the Allen Brain Atlas Mouse Connectivity API.

Notes:
    - Color channels and the projection density images are downloaded at 25 µm resolution by default.
    - Projection density images can be downloaded at 10 µm resolution using the `--download_10um` flag.
    - https://allensdk.readthedocs.io/en/latest/connectivity.html
    - https://allensdk.readthedocs.io/en/stable/_static/examples/nb/mouse_connectivity.html
    - https://alleninstitute.github.io/AllenSDK/allensdk.api.queries.mouse_connectivity_api.html#allensdk.api.queries.mouse_connectivity_api.MouseConnectivityApi
    - Projection density are segmented files that have been warped to CCFv3 with linear interpolation.

Usage:
------
    `download_CCF_aligned_images.py -i 113144533 [-o output_dir] [--download_10um] [-v]`
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
    opts.add_argument('-o', '--output', help='Output dir base path. Default: current working directory (saves to ./<experiment_id>)', default=None, action=SM)
    opts.add_argument('-10', '--download_10um', help='Also download 10 µm projection density images. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def download_CCF_aligned_connectivity_data(experiment_id: int, outdir: str | Path = None):

    mca = MouseConnectivityApi()

    # 1️⃣  Reference-aligned image channel volumes (25 µm)
    outdir = Path(outdir) if outdir else Path().cwd() / str(experiment_id)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    zip_path = outdir / f"{experiment_id}_25um_image_channels.zip"
    print(f"⬇️  Downloading reference-aligned RGB image channels → {zip_path}")
    mca.download_reference_aligned_image_channel_volumes(data_set_id=experiment_id, save_file_path=zip_path)

    # 2️⃣  Projection density volume (25 µm)
    proj_path = Path(outdir) / f"{experiment_id}_projection_density_25um.nrrd"
    print(f"⬇️  Downloading projection density volume → {proj_path}")
    mca.download_projection_density(str(proj_path), experiment_id, 25)
    print(f"✅ Finished downloading experiment {experiment_id}")

def download_CCF_aligned_10um_projection_density(experiment_id: int, outdir: str | Path = None):
    mca = MouseConnectivityApi()

    # Projection density volume (10 µm)
    outdir = Path(outdir) if outdir else Path().cwd() / str(experiment_id)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    proj_path = Path(outdir) / f"{experiment_id}_projection_density_10um.nrrd"
    print(f"⬇️  Downloading 10 µm projection density volume → {proj_path}")
    mca.download_projection_density(str(proj_path), experiment_id, 10)
    print(f"✅ Finished downloading 10 µm projection density for experiment {experiment_id}")

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    output_dir = Path(args.output) if args.output else None

    for exp_id in args.input:
        download_CCF_aligned_connectivity_data(exp_id, output_dir)

    if args.download_10um:
        for exp_id in args.input:
            download_CCF_aligned_10um_projection_density(exp_id, output_dir)

    verbose_end_msg()

if __name__ == '__main__':
    main()
