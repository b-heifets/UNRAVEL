#!/usr/bin/env python3

"""
Use ``CCF30_to_MERFISH30.py`` from UNRAVEL to warp an image from Allen CCFv3 30 um space to MERFISH-CCF 30 um space (30 x 30 x 200 um).

Usage:
------
``CCF30_to_MERFISH30.py`` -m path/image.nii.gz -o path/image_MERFISH30.nii.gz [-f path/MERFISH-CCF_average_template_30um_avg.nii.gz] [-i nearestNeighbor] [-ro path/reg_outputs] [-fri path/fixed_reg_input.nii.gz] [-v]
"""

from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from unravel.warp.to_fixed import forward_warp

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    
    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from 25 um Gubra atlas space', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/image_CCF30.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-f', '--fixed_img', help='Default: /usr/local/unravel/atlases/MERFISH-CCF_30um/MERFISH30f_CCF30m/MERFISH-CCF_average_template_30um_avg.nii.gz', default="/usr/local/unravel/atlases/MERFISH-CCF_30um/MERFISH30f_CCF30m/MERFISH-CCF_average_template_30um_avg.nii.gz", action=SM)
    opts.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor [default], multiLabel, linear, bSpline)', default="nearestNeighbor", action=SM)
    opts.add_argument('-ro', '--reg_outputs', help="Default: /usr/local/unravel/atlases/MERFISH-CCF_30um/MERFISH30f_CCF30m/reg_outputs", default="/usr/local/unravel/atlases/MERFISH-CCF_30um/MERFISH30f_CCF30m/reg_outputs", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Default: /usr/local/unravel/atlases/MERFISH-CCF_30um/MERFISH30f_CCF30m/reg_outputs/MERFISH-CCF_average_template_30um_avg_fixed_reg_input.nii.gz', default='/usr/local/unravel/atlases/MERFISH-CCF_30um/MERFISH30f_CCF30m/reg_outputs/MERFISH-CCF_average_template_30um_avg_fixed_reg_input.nii.gz', action=SM)

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