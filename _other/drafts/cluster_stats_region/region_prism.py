#!/usr/bin/env python3

"""
Create Prism-ready CSVs from a *_merged_sides.csv file.

Input:
    A CSV like:
        condition, sample, cluster_ID, region_ID, abbreviation, region_name,
        cell_count_LH, subregion_volume_LH, cell_count_RH, subregion_volume_RH,
        cell_count_sum, subregion_volume_sum, cell_density

Output:
    One CSV per cluster_ID + region_ID, with replicate values stacked into columns
    by condition, suitable for copy/paste into Prism.

Usage:
------
    region_prism.py -i path/to/file_merged_sides.csv [-c Saline RMDMA SMDMA MBDB MDAI] [-y cell_density] [-o _region_prism] [-v]
"""

from pathlib import Path
import re
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command
from unravel.core.config import Configuration


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Path to *_merged_sides.csv", required=True, action=SM)

    opts = parser.add_argument_group("Optional args")
    opts.add_argument("-c", "--conditions", help="Condition order for Prism columns. Default: alphabetical order in file.", nargs="*", default=None, action=SM)
    opts.add_argument("-y", "--value_col", help="Column to export as Prism replicate values. Default: cell_density", default="cell_density", action=SM)
    opts.add_argument("-o", "--output_dir", help="Output directory. Default: _region_prism", default="_region_prism", action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def sanitize(text: str) -> str:
    text = str(text)
    text = re.sub(r"[^\w.-]+", "_", text)
    return text.strip("_")


def build_prism_table(df: pd.DataFrame, conditions: list[str], value_col: str) -> pd.DataFrame:
    cols = {}
    max_len = 0

    for cond in conditions:
        values = df.loc[df["condition"] == cond, value_col].dropna().reset_index(drop=True)
        cols[cond] = values
        max_len = max(max_len, len(values))

    for cond in conditions:
        cols[cond] = cols[cond].reindex(range(max_len))

    return pd.DataFrame(cols)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose

    input_path = Path(args.input)
    df = pd.read_csv(input_path)

    required_cols = ["condition", "sample", "cluster_ID", "region_ID", "abbreviation", "region_name", args.value_col]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"[red]Missing required columns:[/] {missing}")
        return

    if args.conditions:
        conditions = args.conditions
    else:
        conditions = sorted(df["condition"].dropna().unique().tolist())

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    id_cols = ["cluster_ID", "region_ID", "abbreviation", "region_name"]
    units = df[id_cols].drop_duplicates().sort_values(["cluster_ID", "region_ID"])

    for _, unit in units.iterrows():
        mask = (
            (df["cluster_ID"] == unit["cluster_ID"]) &
            (df["region_ID"] == unit["region_ID"])
        )
        sub_df = df.loc[mask].copy()

        prism_df = build_prism_table(sub_df, conditions, args.value_col)

        cluster_id = unit["cluster_ID"]
        region_id = unit["region_ID"]
        abbr = sanitize(unit["abbreviation"])
        region_name = sanitize(unit["region_name"])

        out_name = f"cluster_{cluster_id}__region_{region_id}__{abbr}__{args.value_col}.csv"
        out_path = output_dir / out_name
        prism_df.to_csv(out_path, index=False)

        if args.verbose:
            print(f"[green]Saved:[/] {out_path}")

    print(f"[green]Done.[/] Output dir: {output_dir}")


if __name__ == "__main__":
    main()