#!/usr/bin/env python3

"""
Load a region_csv output file and merge LH/RH rows into one row per
condition + cluster_ID + region_ID.

Prereqs:
    - region_csv_concat.py

Expected input columns:
    condition, side, cluster_ID, region_ID, abbreviation, region_name,
    cell_count, subregion_volume

Output columns:
    condition, cluster_ID, region_ID, abbreviation, region_name,
    cell_count_LH, subregion_volume_LH,
    cell_count_RH, subregion_volume_RH,
    cell_count_sum, subregion_volume_sum, cell_density

Usage:
------
    region_csv_merge_sides.py -i _region_csv/<file>.csv [-o OUTPUT] [-v]
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command
from unravel.core.config import Configuration


USECOLS = [
    "condition",
    "sample",
    "side",
    "cluster_ID",
    "region_ID",
    "abbreviation",
    "region_name",
    "cell_count",
    "subregion_volume",
]


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Path to input region_csv .csv", required=True, action=SM)

    opts = parser.add_argument_group("Optional args")
    opts.add_argument("-o", "--output", help="Output CSV path. Default: <input_stem>_merged_sides.csv", default=None, action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose

    input_path = Path(args.input)
    df = pd.read_csv(input_path, usecols=USECOLS)

    # Keep only LH/RH rows
    df = df[df["side"].isin(["LH", "RH"])].copy()

    if df.empty:
        print("[red]No LH/RH rows found in input file.[/]")
        return

    # Pivot LH/RH into separate columns
    wide = df.pivot_table(
        index=["condition", "sample", "cluster_ID", "region_ID", "abbreviation", "region_name"],
        columns="side",
        values=["cell_count", "subregion_volume"],
        aggfunc="sum",
        fill_value=0,
    )

    # Flatten MultiIndex columns
    wide.columns = [f"{value}_{side}" for value, side in wide.columns]
    wide = wide.reset_index()

    # Ensure expected columns exist
    for col in [
        "cell_count_LH", "subregion_volume_LH",
        "cell_count_RH", "subregion_volume_RH",
    ]:
        if col not in wide.columns:
            wide[col] = 0

    # Sums
    wide["cell_count_sum"] = wide["cell_count_LH"] + wide["cell_count_RH"]
    wide["subregion_volume_sum"] = wide["subregion_volume_LH"] + wide["subregion_volume_RH"]

    # Density
    wide["cell_density"] = wide["cell_count_sum"] / wide["subregion_volume_sum"]
    wide.loc[wide["subregion_volume_sum"] == 0, "cell_density"] = pd.NA

    # Reorder columns
    out_cols = [
        "condition",
        "sample",
        "cluster_ID",
        "region_ID",
        "abbreviation",
        "region_name",
        "cell_count_LH",
        "subregion_volume_LH",
        "cell_count_RH",
        "subregion_volume_RH",
        "cell_count_sum",
        "subregion_volume_sum",
        "cell_density",
    ]
    wide = wide[out_cols]

    output = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_merged_sides.csv")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(output, index=False)

    print(f"[green]Saved:[/] {output}")


if __name__ == "__main__":
    main()