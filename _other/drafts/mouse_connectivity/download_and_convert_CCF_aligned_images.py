#!/usr/bin/env python3

"""
Use ``download_and_convert_CCF_aligned_images.py`` from UNRAVEL to download connectivity images from the Allen Brain Atlas Mouse Connectivity API and convert them to NIfTI format.
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


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Clean up ".mhd", ".raw", ".zip", ".nrrd" files after conversion


    verbose_end_msg()

if __name__ == '__main__':
    main()
