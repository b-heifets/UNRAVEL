#!/usr/bin/env python3

"""
Use ``mms_seg_summary`` or ``mms_ss`` from UNRAVEL to summarize the prevalence of voxels for somata, endothelial cells, and astrocytes from Ilastik segmentations.

Note:
    - Designed for MMS segmentations of somata (label 1), endothelial cells (3), and astrocytes (4).
    - For each sample, voxel counts and proportions are computed for each cell type.
    - For example, if a sample has 1000 total segmented voxels, with 600 somatic voxels, 300 endothelial voxels, and 100 astroglia voxels, the proportions would be 0.6, 0.3, and 0.1 respectively.

Prereqs:
    - ``seg_ilastik`` outputs (e.g., MMS_seg/MMS_seg_1.nii.gz, MMS_seg/MMS_seg_3.nii.gz, MMS_seg/MMS_seg_4.nii.gz).

Output:
    - Per-sample CSVs saved to <sample>/MMS_seg/<sample>_segmentation_summary.csv
    - Columns: sample, somata_count, endothelial_count, astrocytes_count, total_count, somata_prop, endothelial_prop, astrocytes_prop

Next steps:
    - Use ``agg`` to aggregate results across samples and cd to the target directory.
    - Use ``concat_with_source`` to merge outputs across samples.
    - If most voxels are endothelial, the sample is likely enriched for endothelial cells (manually verify and revise cell type proportions as needed).
    - If most voxels are astroglial, the sample is likely enriched for astrocytes (manually verify and revise cell type proportions as needed).
    
Usage:
------
    mms_seg_summary [-s seg_dir] [-d path/to/dirs] [-p 'ID_*'] [-v]
"""

import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_nii
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--seg_dir', help="Segmentation directory relative to each sample dir. Default: 'MMS_seg'", default="MMS_seg", action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to "ID*" dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: ID_*', default='ID_*', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Add an option(s) to specify which labels to include to make this more generalizable.

def get_seg_voxel_counts(seg_folder, classes):
    counts_dict = {} 
    for label, name in classes.items(): # label: name (e.g., 1: 'somata')
        img_name = f"{seg_folder.name}_{label}.nii.gz"
        img_path = seg_folder / img_name
        if not img_path.exists():
            print(f"[red]Warning: {img_path} does not exist.")
            continue
        img = load_nii(img_path)
        counts_dict[name] = int(np.count_nonzero(img)) # name: count
    return counts_dict

def compute_proportions(counts_dict):
    total_voxel_count = sum(counts_dict.values()) # Total voxel count across all classes (name: count)
    if total_voxel_count == 0:
        return {name: 0.0 for name in counts_dict}
    return {name: counts_dict[name] / total_voxel_count for name in counts_dict} # name: proportion

def process_and_write_line(sample, seg_folder, output_csv, classes):
    counts_dict = get_seg_voxel_counts(seg_folder, classes) # name: count
    total_voxel_count = sum(counts_dict.values()) # Total voxel count across all classes
    proportions_dict = compute_proportions(counts_dict) # name: proportion
    output_csv.write(
        f"{sample},{counts_dict['somata']},{counts_dict['endothelial']},{counts_dict['astrocytes']},{total_voxel_count},{proportions_dict['somata']:.4f},{proportions_dict['endothelial']:.4f},{proportions_dict['astrocytes']:.4f}\n"
    )

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

            labels_dict = {1: 'somata', 3: 'endothelial', 4: 'astrocytes'}
            header = "sample,somata_count,endothelial_count,astrocytes_count,total_count,somata_prop,endothelial_prop,astrocytes_prop\n"

            seg_folder = sample_path / args.seg_dir
            output = sample_path / args.seg_dir / f"{sample_path.name}_segmentation_summary.csv"

            if output.exists():
                print(f"Skipping {sample_path}: '{output}' already exists.")
                continue
            with open(output, 'w') as output_csv:
                output_csv.write(header)
                process_and_write_line(sample_path.name, seg_folder, output_csv, labels_dict)

            progress.update(task_id, advance=1)

    verbose_end_msg()

if __name__ == '__main__':
    main()
