#!/usr/bin/env python3

"""
Use ``gubra_to_CCF.py`` from UNRAVEL to warp an image from gubra 25 um space to Allen CCFv3 30 um space.

Usage:
------
``gubra_to_CCF.py`` -m path/image.nii.gz -o path/image_CCF30.nii.gz [-f path/CCFv3-2017_ano_30um_w_fixes.nii.gz] [-i interpol] [-ro path/reg_outputs] [-fri path/fixed_reg_input.nii.gz] [-v]

Note: 
    - We will use CCFv3 space for future analyses, so this script is used for converting gubra 25 um space to CCFv3 30 um space.

"""

import argparse
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils_rich import SuppressMetavar, SM, CustomHelpAction
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from unravel.warp.to_fixed import forward_warp

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar, add_help=False)
    parser.add_argument('-h', '--help', action=CustomHelpAction, help='Show this help message and exit.', docstring=__doc__)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from 25 um Gubra atlas space', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/image_CCF30.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-f', '--fixed_img', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/CCFv3-2017_ano_30um_w_fixes.nii.gz', default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/CCFv3-2017_ano_30um_w_fixes.nii.gz", action=SM)
    opts.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], multiLabel, linear, bSpline)', default="nearestNeighbor", action=SM)
    opts.add_argument('-ro', '--reg_outputs', help="Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs", default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs/CCFv3-2017_ano_30um_w_fixes__fixed_reg_input.nii.gz', default='/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs/CCFv3-2017_ano_30um_w_fixes__fixed_reg_input.nii.gz', action=SM)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    forward_warp(args.fixed_img, args.reg_outputs, args.fixed_reg_in, args.moving_img, args.interpol, output=args.output)

    verbose_end_msg()


if __name__ == '__main__':
    main()