#!/usr/bin/env python3
"""
Use ``mms_soma_ratio`` or ``sr`` from UNRAVEL to compute the proportion of somata voxels in specified atlas regions.

Note:
    - We used this to compute the proportion of voxels in the anterior commissure containing somata. 
    - This was used to label samples as preferentially having oligodendrocytes.
    - For each seg file, the count of of non-zero voxels in a specified atlas label is divided by the total voxels of that atlas label.
    - If the ratio is > 0.004, the sample is predicted to be oligodendrocyte-enriched.

Prereqs:
    - ``warp_to_atlas`` to warp segmentation volumes to atlas space (e.g., CCFv3 2020 30um).

Output:
    - soma_ratio/<input stem>_soma_ratio.csv
    - Columns: label, count, total_label, proportion.
    - label = atlas label (e.g., 890 for anterior commissure)
    - count = count of nonzero voxels in that label
    - total_label = total voxels of that label in the atlas
    - proportion = count / total voxels of that label in the atlas

Next steps:
    - Use ``mms_concat_with_source`` to concatenate multiple CSVs into one file.  

Usage:
------
    mms_soma_ratio -a path/atlas_CCFv3_2020_30um.nii.gz [-i '<asterisk>_seg_1.nii.gz'] [-l 890] [-o output_dir] [-f] [-v]
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from img_io import load_nii
import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import get_stem, log_command, verbose_start_msg, verbose_end_msg, match_files


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-a', '--atlas', help='Path to (e.g., atlas_CCFv3_2020_30um.nii.gz)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Path(s) to input somatic segmentation file(s) or glob pattern(s). Default: '*_seg_1.nii.gz'", nargs='*', default=['*_seg_1.nii.gz'], action='store', type=str)
    opts.add_argument('-l', '--labels', help='Atlas labels to include (default: 890 for the anterior commissure)', nargs='*', type=int, default=[890])
    opts.add_argument('-o', '--output_dir', help='Output directory. Default: soma_ratio)', default=None, action=SM)
    opts.add_argument('-f', '--force', help='Overwrite existing CSVs', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def soma_ratio(seg_path, atlas_img, labels, out_dir, force):
    
    stem = get_stem(seg_path)

    out_csv = Path(out_dir) / f"{stem}_soma_ratio.csv"
    if out_csv.exists() and not force:
        print(f"{out_csv} exists. Skipping. (Use --force)")
        return

    seg_img = load_nii(seg_path)

    if atlas_img.shape != seg_img.shape:
        raise ValueError("Atlas and segmentation images must have the same shape")

    # Mask seg_img
    mask_img = seg_img > 0
    if mask_img.sum() == 0:
        raise ValueError(f"No voxels >0 found in {Path(seg_path)}")

    # Compute counts and proportions
    records = []
    for lbl in labels:
        voxel_count = int(np.logical_and(mask_img, atlas_img == lbl).sum()) # Count of non-zero voxels in seg_img within the atlas label
        total_label = int((atlas_img == lbl).sum()) # Total voxels in the atlas label
        soma_ratio = voxel_count / total_label if total_label > 0 else 0
        records.append({"label": lbl, "count": voxel_count, "total_label": total_label, "proportion": soma_ratio})

    df = pd.DataFrame(records, columns=["label", "count", "total_label", "proportion"])
    df.to_csv(out_csv, index=False)
    print(f"Output saved to {out_csv}")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    atlas_img = load_nii(args.atlas)

    # Ensure the atlas is uint16
    if atlas_img.dtype != np.uint16:
        print(f"[yellow]⚠️ Warning: Atlas image is {atlas_img.dtype}, converting to uint16.[/yellow]")
        atlas_img = atlas_img.astype(np.uint16)

    # Check if the labels exist in the atlas
    unique_labels = np.unique(atlas_img)
    for lbl in args.labels:
        if lbl not in unique_labels:
            raise ValueError(f"Label {lbl} not found in the atlas labels: {unique_labels}")

    out_dir = Path(args.output_dir) if args.output_dir else Path("soma_ratio")
    out_dir.mkdir(parents=True, exist_ok=True)

    seg_files = match_files(args.input)
    for seg_path in seg_files:
        soma_ratio(seg_path, atlas_img, args.labels, out_dir, args.force)

    verbose_end_msg()

if __name__ == '__main__':
    main()
