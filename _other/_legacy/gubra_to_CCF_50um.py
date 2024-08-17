#!/usr/bin/env python3

"""
Use gubra_to_CCF.py from UNRAVEL to warp an image from gubra 50 um space to Allen CCFv3 50 um space. 
This is useful for warping cell centroids from gubra space to CCFv3 space.

Usage:
------
    for s in sample?? ; do <path>/gubra_to_CCF.py -m ${s}/CCF_space/${s}_consensus_cell_centroids.nii.gz -o ${s}/CCF_space/${s}_consensus_cell_centroids.nii.gz ; done

Next steps:
``io_img_to_points``
``img_resample_points``

Note: 
    This script is used for converting gubra 50 um space to CCFv3 50 um space.

    Update default values for fixed_img, reg_outputs, fixed_reg_in, and interpol as needed.
"""

import argparse
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from unravel.warp.to_fixed import forward_warp

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    # Required arguments
    parser.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from 50 um Gubra atlas space', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/image_CCF50.nii.gz', required=True, action=SM)

    # Optional arguments with default values
    parser.add_argument('-f', '--fixed_img', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/CCFv3-2017_ano_50um_w_fixes.nii.gz', default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/CCFv3-2017_ano_50um_w_fixes.nii.gz", action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], multiLabel, linear, bSpline)', default="nearestNeighbor", action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs", default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs", action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs/CCFv3-2017_ano_50um_w_fixes_fixed_reg_input.nii.gz', default='/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs/CCFv3-2017_ano_50um_w_fixes_fixed_reg_input.nii.gz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
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