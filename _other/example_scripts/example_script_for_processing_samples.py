#!/usr/bin/env python3

"""
Process sample folder(s) w/ a *.czi, tif series, or .nii.gz  image

Run prep_reg.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: ...
outputs: ...

"""

from pathlib import Path
from rich import print
from rich.live import Live

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples

from time import sleep # for example_function

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', action=SM)
    general.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def example_function(img_path, verbose=False):
    """Load a 3D image in the sample folder (first *.czi, *.tif, or *.nii.gz match), print shape and resolution, and mimic processing time"""
    img, xy_res, z_res = load_3D_img(img_path, return_res=True, verbose=verbose)
    print(f"\n    [default]Image shape: {img.shape}, xy_res: {xy_res}, z_res: {z_res}\n")
    sleep(0.5) 
    return img


def main():    
    args = parse_args()
    samples = get_samples(args.dirs, args.pattern)
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            example_function(Path(sample).resolve(), verbose=args.verbose)
            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    from rich.traceback import install
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()