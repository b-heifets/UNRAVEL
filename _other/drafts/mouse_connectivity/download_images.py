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
    opts.add_argument('-d', '--downsample', help='Factor to downsample images by (e.g., 2 = half size). Default: no downsampling', type=int, default=1, action=SM)
    opts.add_argument('-o', '--output', help='Path to output dir for images. Default: connectivity', default='connectivity', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # This could be used to download full resolution section images (.jpg)
    # from allensdk.api.queries.image_download_api import ImageDownloadApi
    # img_api = ImageDownloadApi()
    # section_images = img_api.section_image_query(section_data_set_id=experiment_id)
    # print(section_images[0])

    verbose_end_msg()

if __name__ == '__main__':
    main()
