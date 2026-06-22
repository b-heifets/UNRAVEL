#!/usr/bin/env python3

"""
Fix abbreviation and region_name columns in CSVs using region_ID.

Uses match_files() to find CSVs, then refreshes:
    - abbreviation
    - region_name

based on a lookup from a CCFv3 info CSV.

Usage:
------
    fix_region_labels.py -i "*.csv" [-csv CCFv3-2020_info.csv] [-idc lowered_ID] [--inplace] [-v]
"""

from pathlib import Path
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files
from unravel.core.config import Configuration


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group("Optional args")
    opts.add_argument("-i", "--input", help='Pattern(s) for CSVs to fix. Default: "*.csv"', nargs="*", default=["*.csv"], action=SM)
    opts.add_argument("-csv", "--info_csv_path", help="CSV name or path/name.csv. Default: CCFv3-2020_info.csv", default="CCFv3-2020_info.csv", action=SM)
    opts.add_argument("-idc", "--region_id_col", help="Column in info CSV to use for region IDs. Default: lowered_ID", default="lowered_ID", choices=["lowered_ID", "structure_ID"], action=SM)
    opts.add_argument("--inplace", help="Overwrite input CSVs instead of writing *_fixed.csv copies.", action="store_true", default=False)
    opts.add_argument("--suffix", help="Suffix for non-inplace outputs. Default: _fixed", default="_fixed", action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def load_ccfv3_lookup(info_csv_path, region_id_col="lowered_ID"):
    """Load region lookup from a built-in or user-provided CCFv3 info CSV."""
    columns_to_load = [region_id_col, "abbreviation", "full_structure_name"]

    if info_csv_path in ["CCFv3-2017_info.csv", "CCFv3-2020_info.csv"]:
        info_df = pd.read_csv(
            Path(__file__).parent.parent.parent.parent / "unravel" / "core" / "csvs" / info_csv_path,
            usecols=columns_to_load,
        )
    else:
        info_df = pd.read_csv(info_csv_path, usecols=columns_to_load)

    info_df[region_id_col] = pd.to_numeric(info_df[region_id_col], errors="coerce")

    lookup = {}
    for _, row in info_df.iterrows():
        if pd.isna(row[region_id_col]):
            continue
        lookup[int(row[region_id_col])] = {
            "abbreviation": row["abbreviation"] if pd.notna(row["abbreviation"]) else np.nan,
            "region_name": row["full_structure_name"] if pd.notna(row["full_structure_name"]) else np.nan,
        }

    return lookup


def fix_one_csv(csv_path, lookup, inplace=False, suffix="_fixed", verbose=False):
    df = pd.read_csv(csv_path)

    if "region_ID" not in df.columns:
        if verbose:
            print(f"[yellow]Skipping {csv_path.name}: no region_ID column[/]")
        return None

    region_ids = pd.to_numeric(df["region_ID"], errors="coerce")

    df["abbreviation"] = region_ids.map(
        lambda x: lookup.get(int(x), {}).get("abbreviation", np.nan) if pd.notna(x) else np.nan
    )
    df["region_name"] = region_ids.map(
        lambda x: lookup.get(int(x), {}).get("region_name", np.nan) if pd.notna(x) else np.nan
    )

    if inplace:
        out_path = csv_path
    else:
        out_path = csv_path.with_name(f"{csv_path.stem}{suffix}{csv_path.suffix}")

    df.to_csv(out_path, index=False)

    if verbose:
        n_found = region_ids.map(lambda x: int(x) in lookup if pd.notna(x) else False).sum()
        print(f"[green]Saved:[/] {out_path} [dim]({n_found}/{len(df)} rows matched)[/]")

    return out_path


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose

    lookup = load_ccfv3_lookup(args.info_csv_path, region_id_col=args.region_id_col)

    csv_files = []
    for pat in args.input:
        csv_files.extend(match_files(pat))

    # de-duplicate while preserving order
    seen = set()
    csv_files = [Path(p) for p in csv_files if not (str(p) in seen or seen.add(str(p)))]

    if not csv_files:
        print("[red]No matching CSV files found.[/]")
        return

    if args.verbose:
        print(f"[bold]CSV files to fix:[/]")
        for f in csv_files:
            print(f"  {Path(f).name}")

    for csv_path in csv_files:
        fix_one_csv(
            Path(csv_path),
            lookup,
            inplace=args.inplace,
            suffix=args.suffix,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    main()