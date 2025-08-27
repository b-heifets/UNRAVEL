#!/usr/bin/env python3

"""
Use ``gta_simplify_metadata`` (``gta_sm``) from UNRAVEL to simplify metadata from the Genetic Tools Atlas (GTA). 

Prereqs:
    - Visit the GTA: https://portal.brain-map.org/genetic-tools/genetic-tools-atlas
    - Click "Access Genetic Tools Atlas"
    - Filter by 'Data Modality' = 'STPT'
    - 'Download Data' → 'Metadata Table'
    - Unzip the downloaded file, find SpecimenMetadata.csv, and use it as the input.

Note:
    - Default columns to keep: 'Image Series ID' 'Donor Genotype' 'Vector Full Name' 'Targeted Cell Population' 'Cargo' 'Vector Delivery Method'
    - Duplicate rows in 'Image Series ID' are dropped.
    - The output file is saved as 'SpecimenMetadata_subset.csv' in the current directory.
    - If you want to keep other columns, use the -col option with a space-separated list of column names.
    - If you want to change the output file name, use the -o option.

Next steps:
    - Run ``gta_org_samples`` (``gta_os``) to organize the GTA data across samples for batch processing.

Usage:
------
    gta_sm -i "path/to/SpecimenMetadata.csv" [-col col1 col2 ...] [-o output] [-v]
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

COLUMNS = ['Image Series ID', 'Donor Genotype', 'Vector Full Name', 'Targeted Cell Population', 'Cargo', 'Vector Delivery Method']

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='Path to the SpecimenMetadata.csv. Default: SpecimenMetadata.csv in the current directory', default='SpecimenMetadata.csv', action=SM)
    opts.add_argument('-col', '--columns', help='CSV columns to keep. See notes for default columns.', nargs='*', default=COLUMNS, action=SM)
    opts.add_argument('-o', '--output', help='Output CSV file path. Default: SpecimenMetadata_subset.csv', default='SpecimenMetadata_subset.csv', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    df = pd.read_csv(args.input)

    missing = [c for c in args.columns if c not in df.columns]
    if missing:
        print(f"[yellow]Warning: Missing columns: {missing}[/yellow]")
        args.columns = [c for c in args.columns if c in df.columns]

    # Keep specified columns
    if args.columns:
        df = df[args.columns]

    # Drop rows duplicate values in 'Image Series ID'
    df = df.drop_duplicates(subset='Image Series ID')

    # Fill blank cells with 'NA'
    df = df.fillna('NA')

    # Save the edited DataFrame
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    verbose_end_msg()
    

if __name__ == "__main__":
    main()
