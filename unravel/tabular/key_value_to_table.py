#!/usr/bin/env python3

"""
Use ``tabular_key_value_to_table`` or ``kv_table`` from UNRAVEL to convert structured key-value data into a tabular format.

Input file format:
    - Format: <key><delimiter><value>, one pair per line or row
    - Groups of key-value pairs (separated by repeated first key) form rows in the output.
    - Example (txt or 2-col csv/xlsx):
    - cluster,1
    - Pearson correlation,-0.1567
    - p-value,0.2359
    - cluster,2
    - Pearson correlation,0.1376
    - p-value,0.4449

Output file format:
    - A tabular file (.csv or .xlsx) where each key becomes a column header, and each group forms a row.
    - Example:
    - cluster, Person_correlation, p_value
    - 1, -0.1567, 0.2359
    - 2, 0.1376, 0.4449

Usage:
------
    tabular_key_value_to_table -i input.csv [-o output.csv] [-d ,] [-v]
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.tabular.utils import load_tabular_file, save_tabular_file


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input file (.txt, .csv, or .xlsx)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-d', '--delimiter', help="Delimiter for text input. Default: ','.", default=',', action=SM)
    opts.add_argument('-o', '--output', help="Path to the output file (.csv or .xlsx). Default: input with .csv extension.", default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def reshape_key_value_blocks(pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """Reshape a list of key-value pairs into a table (one row per group)."""
    structured_data = []
    current_row = {}
    first_key = pairs[0][0] if pairs else None

    for key, value in pairs:
        key = key.strip().replace(" ", "_")
        if key == first_key and current_row:
            structured_data.append(current_row)
            current_row = {}
        current_row[key] = value.strip()
    if current_row:
        structured_data.append(current_row)

    return pd.DataFrame(structured_data).fillna(pd.NA)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load and parse key-value pairs
    input_path = Path(args.input)
    suffix = input_path.suffix.lower()

    if suffix == '.txt':
        lines = input_path.read_text(encoding='utf-8').strip().splitlines()
        raw_pairs = [line.split(args.delimiter, 1) for line in lines if args.delimiter in line]
    elif suffix in ['.csv', '.xlsx']:
        df, _ = load_tabular_file(args.input)
        if df.shape[1] != 2:
            raise ValueError(f"Input file must have exactly 2 columns for key-value structure. Found {df.shape[1]}")
        
        if args.skip_header:
            df = df.iloc[1:]
        raw_pairs = list(df.itertuples(index=False, name=None))

    else:
        raise ValueError(f"Unsupported file format: {args.input}")

    df_out = reshape_key_value_blocks(raw_pairs)

    # Determine output path
    default_ext = '.xlsx' if suffix == '.xlsx' else '.csv'
    output_path = args.output or str(input_path.with_suffix(default_ext))
    save_tabular_file(df_out, output_path, index=False, verbose=args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()
