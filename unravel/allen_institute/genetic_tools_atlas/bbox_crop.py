#!/usr/bin/env python3

"""
Use ``gta_bbox_crop`` (``gta_bc``) from UNRAVEL to crop an image using a bounding box and save it as a TIFF series.

Note:
    - For simplicity and processing with Ilastik, this outputs as a TIFF series.
    - The TIFF series can be converted with ``io_convert_img`` (``conv``) to other formats if needed.

Usage:
------
    bbox_crop [-i red] [-a green] [--force] [-d ID_123 ID_456 ...] [-p pattern] [-v]
"""

from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.img_tools import crop
from unravel.core.utils import get_samples, get_stem, initialize_progress_bar, log_command, verbose_start_msg, verbose_end_msg, load_text_from_file


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-i', '--input', help='Name of a directory with TIFFs in the "ID_*" directories. Default: red', default='red', action=SM)
    opts.add_argument('-a', '--auto_crop_dir', help='Name of the directory with TIFFs used for ``gta_auto_crop`` (for the bounding box .txt path). Default: green', default='green', action=SM)
    opts.add_argument('-f', '--force', help='Force overwrite existing output files. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to "ID*" dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: ID_*', default='ID_*', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            img_path = sample_path / args.input

            img_stem = get_stem(img_path)
            output_dir = img_path.parent / f"{img_stem}_cropped"
            if not args.force and output_dir.exists():
                print(f"[red]Output directory {output_dir} already exists. Use -f to overwrite.[/red]")
                continue

            if args.force and output_dir.exists():
                for file in output_dir.iterdir():
                    file.unlink()

            output_dir.mkdir(parents=True, exist_ok=True)

            img = load_3D_img(img_path, desired_axis_order='zyx', verbose=args.verbose)

            bbox_path = sample_path / f"bbox/{args.auto_crop_dir}_bbox_pad_zyx.txt"
            if not bbox_path.exists():
                print(f"[red]Missing bbox file from ``gta_auto_crop``: {bbox_path}[/red]")
                continue
            bbox = load_text_from_file(bbox_path)
            img_cropped = crop(img, bbox)

            save_as_tifs(img_cropped, output_dir, ndarray_axis_order='zyx')

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()