#!/usr/bin/env python3

"""
Use ``gubra_to_CCF.py`` from UNRAVEL to warp an image from gubra 50 um space to Allen CCFv3 50 um space. 
This is useful for warping cell centroids from gubra space to CCFv3 space.

Usage:
------
``gubra_to_CCF.py`` -m path/image.nii.gz -o path/image_CCF50.nii.gz [-f path/CCFv3-2017_ano_50um_w_fixes.nii.gz] [-i interpol] [-ro path/reg_outputs] [-fri path/fixed_reg_input.nii.gz] [-v]

Note: 
    - This script is used for converting gubra 50 um space to CCFv3 50 um space.

Next steps:
    ``io_img_to_points``
    ``img_resample_points``

"""

from rich import print
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from unravel.warp.to_fixed import forward_warp

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from 50 um Gubra atlas space', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/image_CCF50.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-f', '--fixed_img', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/CCFv3-2017_ano_50um_w_fixes.nii.gz', default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/CCFv3-2017_ano_50um_w_fixes.nii.gz", action=SM)
    opts.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], multiLabel, linear, bSpline)', default="nearestNeighbor", action=SM)
    opts.add_argument('-ro', '--reg_outputs', help="Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs", default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs/CCFv3-2017_ano_50um_w_fixes_fixed_reg_input.nii.gz', default='/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m_50um/reg_outputs/CCFv3-2017_ano_50um_w_fixes_fixed_reg_input.nii.gz', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

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