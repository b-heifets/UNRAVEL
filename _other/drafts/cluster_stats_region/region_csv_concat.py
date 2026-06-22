#!/usr/bin/env python3

"""
Concatenate region-level CSVs in the current working directory into one CSV.

Prereqs:
    - ``cstats_org_data``, ``cstats_group_data``, ``prepend``

Expected filename pattern:
    condition_sampleXXX__...csv
or similar, where:
    - condition = first token before '_'
    - side = LH or RH if the filename stem ends with _LH or _RH

Default kept columns:
    cluster_ID, region_ID, abbreviation, region_name, cell_count, subregion_volume

Output:
    _region_csv/<cwd>.csv

Usage:
------
    region_csv_concat.py [-k COLS [COLS ...]] [-o OUTPUT] [-v]
        
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files
from unravel.core.config import Configuration


DEFAULT_KEEP_COLS = [
    "cluster_ID",
    "region_ID",
    "abbreviation",
    "region_name",
    "cell_count",
    "subregion_volume",
]


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group("Optional args")
    opts.add_argument("-k", "--keep_cols", help="Columns to keep from input CSVs. Default: cluster_ID region_ID abbreviation region_name cell_count subregion_volume", nargs="*", default=DEFAULT_KEEP_COLS, action=SM)
    opts.add_argument("-o", "--output", help="Output CSV path. Default: _region_csv/<cwd>.csv", default=None, action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()

# TODO: compute the cell density (useful for unilateral data). This could be dropped when loading in the next script) 

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose

    csv_files = match_files("*.csv")

    dfs = []
    for path in csv_files:
        df = pd.read_csv(path, usecols=args.keep_cols)

        # Add the condition and side columns based on the filename
        condition = str(path.name).split("_")[0]
        sample = str(path.name).split("_")[1]
        side = str(path.stem).split("_")[-1]
        df["condition"] = condition
        df["sample"] = sample
        df["side"] = side

        # Reorder columns to have condition and side first
        cols = ["condition", "sample", "side"] + [c for c in args.keep_cols if c in df.columns]
        df = df[cols]
        dfs.append(df)

    out_df = pd.concat(dfs, ignore_index=True)

    output = Path(args.output) if args.output else Path.cwd() / f"_region_csv/{Path.cwd().name}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output, index=False)

    print(f"[green]Saved:[/] {output}")


if __name__ == "__main__":
    main()