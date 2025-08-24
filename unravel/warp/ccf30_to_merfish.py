#!/usr/bin/env python3

"""
Use ``warp_ccf30_to_merfish`` or ``c2m`` from UNRAVEL to warp an image from Allen CCFv3 30 um space to MERFISH-CCF space (10 x 10 x 200 µm).

Prereqs:
    - Download files for warping (CCF30_to_MERFISH.tar.gz) from:
    - https://stanfordmedicine.box.com/s/u9vg2wdmrx1t4bvqu321vmggg793kvuo (This is 1.4 GB)
    - Extract it (double click or use tar -xvzf CCF30_to_MERFISH.tar.gz) to a folder (e.g., /path/CCF30_to_MERFISH; this is the warp root).
    - This folder should contain:
    - MERFISH_resampled_average_template.nii.gz
    - reg_outputs/MERFISH_resampled_average_template_fixed_reg_input.nii.gz
    - reg_outputs/ANTsPy_`*`

Usage:
------
warp_ccf30_to_merfish -i path/image.nii.gz -o path/to/output_dir -w path/to/warp_root [-inp nearestNeighbor] [-v]
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import get_stem, log_command, match_files, verbose_start_msg, verbose_end_msg, initialize_progress_bar
from unravel.warp.to_fixed import forward_warp


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    
    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='One or more .nii.gz files or glob patterns to warp from CCFv3 30 µm atlas space (e.g., *.nii.gz subdir/*.nii.gz)', nargs='*', required=True, action=SM)
    reqs.add_argument('-w', '--warp_root', help='Path to the root directory containing the warp files.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Output directory to save warped images. Each output will be named like inputname_MERFISH.nii.gz. Default: MERFISH/', default="MERFISH", action=SM)
    opts.add_argument('-inp', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor \[default], multiLabel, linear, bSpline)', default="nearestNeighbor", action=SM)
    opts.add_argument('-n', '--workers', help='Number of parallel workers to use. Default: 10', default=10, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def ccf30_to_merfish(input_img_path, warp_root, output_img_path, interpol="nearestNeighbor"):
    root = Path(warp_root)
    fixed_img_path = root / "MERFISH_resampled_average_template.nii.gz"
    fixed_reg_in = "MERFISH_resampled_average_template_fixed_reg_input.nii.gz"
    reg_outputs_path = root / "reg_outputs"

    forward_warp(fixed_img_path, reg_outputs_path, fixed_reg_in, input_img_path, interpol, output=output_img_path, pad_percent=0.15)

    # Delete the intermediate warped image
    warp_outputs_dir = reg_outputs_path / "warp_outputs"
    warped_nii_path = Path(str(warp_outputs_dir / str(Path(input_img_path).name).replace(".nii.gz", "_in_fixed_img_space.nii.gz")))
    if warped_nii_path.exists():
        warped_nii_path.unlink()
    
    # Delete the warp_outputs directory if empty
    if warp_outputs_dir.exists() and not any(warp_outputs_dir.iterdir()):
        warp_outputs_dir.rmdir()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_img_paths = match_files(args.input)

    progress, task_id = initialize_progress_bar(len(input_img_paths), task_message="[bold green]Downloading Zarr datasets...")
    with Live(progress):

        def wrapped_download(input_img_path, output_img_path=None):
            ccf30_to_merfish(input_img_path, args.warp_root, output_img_path, args.interpol)
            progress.update(task_id, advance=1)
    
        # Download each experiment ID in parallel
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            futures = []
            for input_img_path in input_img_paths:
                img_stem = get_stem(input_img_path)
                output_img_path = output_dir / f"{img_stem}_MERFISH.nii.gz"
                futures.append(executor.submit(wrapped_download, input_img_path, output_img_path))
            for f in as_completed(futures):
                try:
                    f.result()  # This will raise any exceptions from the thread
                except Exception as e:
                    print(f"[red]Exception occurred:[/red] {e}")

    verbose_end_msg()


if __name__ == '__main__':
    main()