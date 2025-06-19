#!/usr/bin/env python3

"""
Use ``CCF30_to_gubra.py`` from UNRAVEL to warp an image from Allen CCFv3 30 um space to gubra 25 um space.

Usage:
------
``CCF30_to_gubra.py`` -m path/CCF30_image.nii.gz -o path/image_gubra_space.nii.gz [-a path/atlas.nii.gz] [-inp nearestNeighbor] [-fri path/fixed_reg_input.nii.gz] [-pad 0.25] [-dt uint16] [-v]
"""

from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_nii
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from unravel.warp.to_atlas import to_atlas


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    
    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from CCFv3 30 um space', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/image_gubra_space.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-a', '--atlas', help='path/atlas.nii.gz or template matching moving image. Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/gubra_ano_combined_25um_w_fixes.nii.gz', default='/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/gubra_ano_combined_25um_w_fixes.nii.gz', action=SM)
    opts.add_argument('-inp', '--interpol', help='Interpolator for ants.apply_transforms (multiLabel \[default],  nearestNeighbor, linear, bSpline)', default="multiLabel", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs/CCFv3-2017_ano_30um_w_fixes__fixed_reg_input.nii.gz', default='/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs/CCFv3-2017_ano_30um_w_fixes__fixed_reg_input.nii.gz', action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Percentage of padding that was added to each dimension of the fixed image during ``reg``. Default: 0.25 (25%%).', default=0.25, type=float, action=SM)
    opts.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    reg_path = Path(args.fixed_reg_in).parent
    img = load_nii(args.moving_img)

    # Warp an image from Allen CCFv3 30 um space to gubra 25 um space
    to_atlas(reg_path, 
             img, 
             args.fixed_reg_in, 
             args.atlas, 
             args.output, 
             args.interpol, 
             dtype=args.dtype, 
             pad_percent=args.pad_percent)

    verbose_end_msg()


if __name__ == '__main__':
    main()