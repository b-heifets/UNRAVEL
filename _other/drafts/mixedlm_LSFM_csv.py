#!/usr/bin/env python3

"""
Use ``mixedlm_csv.py`` from UNRAVEL to generate a CSV for smf.mixedlm() analysis, containing region-wise intensities for X and Y images.

Inputs:
    - Y-axis images: e.g., cFos maps (first word = group, second word = mouse ID).

Output:
    - CSV with columns: Group, MouseID, RegionID, cFos, Gene1, Gene2, ...
    
Usage:
------
    mixedlm_csv.py -x path/x_axis_image_<asterisk>.nii.gz -y path/y_axis_image_<asterisk>.nii.gz -a path/atlas.nii.gz -o output.csv [-mas path/mask1.nii.gz]
"""

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from glob import glob
from pathlib import Path
from rich import print
from rich.progress import Progress, BarColumn, TextColumn
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command
from unravel.core.img_io import load_nii
from unravel.region_stats.rstats_mean_IF import calculate_mean_intensity
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-y', '--y_img_glob', help='path/y_axis_image_*.nii.gz (e.g., glob pattern for cFos maps).', required=True, action=SM)
    reqs.add_argument('-a', '--atlas', help='path/atlas.nii.gz.', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/output.csv.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', default=None, action=SM)
    opts.add_argument('-yv', '--y_var', help='Name of the Y-axis variable (e.g., cFos). Default: cFos', default='cFos', action=SM)

    return parser.parse_args()


def calculate_mean_intensities_parallel_lsfm(img_path, atlas_img, region_ids):
    """Extracts region-wise mean intensities for an X image."""
    try:
        group, mouse_id = Path(img_path).stem.split('_')[:2]
        img = load_nii(img_path)
        region_mean_dict = calculate_mean_intensity(atlas_img, img, regions=region_ids)
        return group, mouse_id, region_mean_dict
    except Exception as e:
        print(f"[red]    Error processing {img_path}: {e}")
        return None


@log_command
def main():
    install()
    args = parse_args()

    # Load atlas and masks
    print("\n    Loading atlas and masks...")
    atlas_img = load_nii(args.atlas)
    mask_img = np.logical_and.reduce([load_mask(m) for m in args.masks]) if args.masks else np.ones_like(atlas_img, dtype=bool)
    atlas_img = np.where(mask_img, atlas_img, 0)
    region_ids = np.unique(atlas_img[atlas_img > 0])

    # Collect image paths
    img_paths = [Path(file) for file in sorted(glob(args.y_img_glob))]
    if not img_paths:
        print("\n    [red]No images found. Exiting...\n")
        return

    # Collect Y-axis image paths
    print(f"\n    Processing {len(img_paths)} images...\n")
    all_results = []
    with Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), "[progress.percentage]{task.percentage:>3.0f}%") as progress:
        task = progress.add_task("Processing images...", total=len(img_paths))

        futures = []
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(calculate_mean_intensities_parallel_lsfm, img_path, atlas_img, region_ids)
                for img_path in img_paths
            ]

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    group, mouse_id, region_mean_dict = result
                    for region, mean in region_mean_dict.items():
                        all_results.append({
                            'Group': group,
                            'MouseID': mouse_id,
                            'RegionID': region,
                            args.y_var: mean
                        })
                progress.advance(task)

    # Create a dataframe from results
    results_df = pd.DataFrame(all_results)

    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False)

if __name__ == '__main__':
    main()
