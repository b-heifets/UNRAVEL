#!/usr/bin/env python3

"""
Use ``gubra_to_CCF30.py`` from UNRAVEL to warp an image from gubra 25 um space to Allen CCFv3 30 um space.

Note: 
    - We will use CCFv3 space for future analyses, so this script is used for converting gubra 25 um space to CCFv3 30 um space.

Next steps:
    - For resampling to the standard 10x10x10 um resolution, use: ``resample``
    - For warping to MERFISH-CCF space, use: ``CCF30_to_MERFISH.py`

Usage:
------
``gubra_to_CCF30.py`` -m path/image.nii.gz -o path/image_CCF30.nii.gz [-f path/CCFv3-2017_ano_30um_w_fixes.nii.gz] [-inp linear] [-ro path/reg_outputs] [-fri path/fixed_reg_input.nii.gz] [-v]
"""

from pathlib import Path
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
    opts.add_argument('-inp', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor \[default], multiLabel, linear, bSpline)', default="nearestNeighbor", action=SM)
    opts.add_argument('-f', '--fixed_img', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/CCFv3-2017_ano_30um_w_fixes.nii.gz', default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/CCFv3-2017_ano_30um_w_fixes.nii.gz", action=SM)
    opts.add_argument('-ro', '--reg_outputs', help="Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs", default="/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Default: /usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs/CCFv3-2017_ano_30um_w_fixes__fixed_reg_input.nii.gz', default='/usr/local/unravel/atlases/gubra_to_CCF/CCF-f__Gubra-m/reg_outputs/CCFv3-2017_ano_30um_w_fixes__fixed_reg_input.nii.gz', action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Percentage of padding that was added to each dimension of the fixed image during ``reg``. Default: 0.15 (15%%).', default=0.15, type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    print(f'\n{args.interpol=}\n')
    print(f'\n{type(args.interpol)=}\n')
    import sys ; sys.exit()

    forward_warp(args.fixed_img, args.reg_outputs, args.fixed_reg_in, args.moving_img, args.interpol, output=args.output, pad_percent=args.pad_percent)

    # Delete the intermediate warped image
    warp_outputs_dir = Path(args.reg_outputs) / "warp_outputs" 
    warped_nii_path = Path(str(warp_outputs_dir / str(Path(args.moving_img).name).replace(".nii.gz", "_in_fixed_img_space.nii.gz")))
    if warped_nii_path.exists():
        warped_nii_path.unlink()

    verbose_end_msg()


if __name__ == '__main__':
    main()