#!/usr/bin/env python3

"""
[dark_green]Example of forward warping atlas to tissue space: [/]
[bold bright_magenta]warp.py[/] [cyan bold]-m atlas_img.nii.gz -f reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -o warp/atlas_in_tissue_space.nii.gz[/] [purple4]-ro reg_outputs -inp multiLabel -v [/]

[dark_green]Example of inverse warping tissue to atlas space: [/]
[bold bright_magenta]warp.py[/] [cyan bold]-m reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -f atlas_img.nii.gz -o warp/tissue_in_atlas_space.nii.gz[/] [purple4]-ro reg_outputs -inv -v [/]

[dark_green]Prereq:[/]
reg.py
"""

import argparse
import sys
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils_rich import SuppressMetavar, SM
from unravel.core.config import Config
        
cfg = Config(Path(__file__).parent / 'test.ini')
print(type(cfg.test.a))

def parse_args():
    parser = argparse.ArgumentParser(description='Script description',formatter_class=SuppressMetavar)
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument('-info', '--info', help='Print extended help information and exit.', action='store_true')
    args, _ = pre_parser.parse_known_args()

    if args.info:
        print(__doc__)
        sys.exit()

    reqs = parser.add_argument_group('Required arguments')
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM) # Offload to config file
    parser.add_argument('-d', '--dirs', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/input', required=True, action=SM)
    reqs.add_argument('-ro', '--reg_outputs', help='path/reg_outputs', required=True, action=SM)
    reqs.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-m', '--moving_img', help='path/moving_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/output.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-inv', '--inverse', help='Perform inverse warping (use flag if -f & -m are opposite from reg.py)', default=False, action='store_true')
    opts.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default], nearestNeighbor, multiLabel).', default='bSpline', action=SM)
    parser.epilog = """Usage: warp.py -m path/moving_image.nii.gz -f path/fixed_image.nii.gz -o path/output.nii.gz -ro path/reg_outputs -v"""
    return parser.parse_args()


def main(): 
    args = parse_args()

    reg_outputs_path = Path(args.reg_outputs).resolve()
    moving_img_path = str(Path(args.moving_img).resolve())
    fixed_img_path = str(Path(args.fixed_img).resolve())

    print(f'\n{reg_outputs_path=}\n')
    print(f'{moving_img_path=}\n')
    print(f'{fixed_img_path=}\n')

if __name__ == '__main__': 
    install()
    main()























from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

from unravel.core.config import Configuration



@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()


    verbose_end_msg()



if __name__ == '__main__':
    main()


# Search for print_cmd_and_times and remove it.
# Reinstall on my computer and cb in windy and dev. Email Windy and Peter back. Shamloo










