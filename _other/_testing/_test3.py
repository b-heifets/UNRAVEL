#!/usr/bin/env python3

"""
Use ``test`` from UNRAVEL to ...
Testing script description line 2.

Prereqs:
    reg.py

Inputs:
    - path/moving_image.nii.gz
    - path/fixed_image.nii.gz

Outputs:
    - path/output.nii.gz

Note:
    - Use the flag -inv if the -f and -m inputs are opposite from reg.py.

Usage for forward warping atlas to tissue space:
------------------------------------------------
    test -m atlas_img.nii.gz -f reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -o warp/atlas_in_tissue_space.nii.gz [-ro reg_outputs] [-inp multiLabel] [-v]

Usage for inverse warping tissue to atlas space:
------------------------------------------------
    test -m reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -f atlas_img.nii.gz -o warp/tissue_in_atlas_space.nii.gz [-ro reg_outputs] [-inv] [-v]
"""

from rich import print
from rich.text import Text

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

# "[red1]U[/][dark_orange]N[/][bold gold1]R[/][green]A[/][bright_blue]V[/][purple3]E[/][bright_magenta]L[/]"

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/input', required=True, action=SM)
    reqs.add_argument('-ro', '--reg_outputs', help='path/reg_outputs', required=True, action=SM)
    reqs.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-m', '--moving_img', help='path/moving_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/output.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-inv', '--inverse', help='Perform inverse warping (use flag if -f & -m are opposite from reg.py)', default=False, action='store_true')
    opts.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default], nearestNeighbor, multiLabel).', default='bSpline', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
