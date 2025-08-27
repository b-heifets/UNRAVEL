#!/usr/local/fsl/fslpython/envs/fslpython/bin/python

"""
Run fsleyes with given display range and files.
"""

import subprocess

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from utils import match_files


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-max', '--display_range_max', help='Maximum display range value.', required=True, type=float)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="List of .nii.gz file paths or glob patterns (space-separated). Default: '*.nii.gz'", nargs='*', default='*.nii.gz', action=SM)
    opts.add_argument('-min', '--display_range_min', help='Minimum display range value.', default=0, type=float)
    opts.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)

    return parser.parse_args()

def main():
    args = parse_args()
    
    # Build the fsleyes command
    fsleyes_command = ['fsleyes']
    image_files = match_files(args.input)
    for image_file in image_files:
        fsleyes_command.extend([image_file, '-dr', str(args.display_range_min), str(args.display_range_max)])
    fsleyes_command.extend([args.atlas, '-ot', 'label', '-o'])
    
    # Run fsleyes command
    subprocess.run(fsleyes_command)

if __name__ == "__main__":
    main()
