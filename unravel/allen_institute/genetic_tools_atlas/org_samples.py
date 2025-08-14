#!/usr/bin/env python3

"""
Use ``gta_org_samples`` (``gta_os``) from UNRAVEL to organize GTA data across samples for batch processing.

Prereqs:
    - ``gta_download`` (``gta_dl``) must be run first to download the data.
    - Download STPT metadata from the GTA: https://portal.brain-map.org/genetic-tools/genetic-tools-atlas
    - Optional: ``gta_metadata`` (``gta_m``) may be run to simplify the metadata used to sort the samples (AAVs or Tg lines).

Note:
    - Key SpecimenMetadata.csv columns: 'Image Series ID' 'Vector Delivery Method'
    - Run from GTA_level_3 directory
    - Tiff series for each sample will be grouped together in a sample directory.
    - AAV samples will be grouped together, and Tg samples will be grouped together.

Usage:
------
    gta_os -i "path/to/SpecimenMetadata.csv" [-col col1 col2 ...] [-o output_dir/] [-v]
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

COLUMNS = ['Image Series ID', 'Vector Delivery Method']

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='Path to the SpecimenMetadata.csv. Default: SpecimenMetadata.csv or SpecimenMetadata_subset.csv in the current directory', default='SpecimenMetadata.csv', action=SM)
    opts.add_argument('-col', '--columns', help='CSV columns to keep. See notes for default columns.', nargs='*', default=COLUMNS, action=SM)
    opts.add_argument('-o', '--output_dir', help='Output directory for organized samples', default='GTA_samples', action=SM)
    opts.add_argument('-p', '--prefix', help='Prefix for sample directories (useful for batch processing). Default: "sample_"', default='sample_', action=SM)
    opts.add_argument('-d', '--directories', help='Space-separated list of tif directory names to organize. Default: "red green"', default=['red', 'green'], nargs='*', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def org_samples(aav_samples_df, target_dir, prefix, tif_dirs):
    """
    Organize AAV samples into directories based on the SpecimenMetadata DataFrame.

    Parameters:
    -----------
    aav_samples_df : pd.DataFrame
        DataFrame containing AAV samples with 'Image Series ID' and 'Vector Delivery Method'.
    target_dir : Path
        Directory where the sample directories will be created.
    prefix : str
        Prefix for sample directories.
    tif_dirs : list of str
        List of TIFF directory names to organize.
    """
    for _, row in aav_samples_df.iterrows():
        series_id = row['Image Series ID']
        sample_dir = target_dir / f'{prefix}{series_id}'
        sample_dir.mkdir(parents=True, exist_ok=True)

        for dir in tif_dirs:
            tif_dir = Path(dir) / str(series_id)
            if tif_dir.is_dir():
                dest = sample_dir / tif_dir.name
                if dest.exists():
                    print(f"[yellow]Destination already exists, skipping:[/yellow] {dest}")
                else:
                    print(f"Moving {tif_dir} to {sample_dir}")
                    tif_dir.rename(dest)
            else:
                print(f"[yellow]Directory not found: {tif_dir}[/yellow]")
    

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    if not input_path.is_file():
        fallback = Path('SpecimenMetadata_subset.csv')
        input_path = fallback if fallback.is_file() else input_path
    if not input_path.is_file():
        print(f"[bold red]Input file not found:[/bold red] {input_path}")
        return

    df = pd.read_csv(input_path)

    missing = [c for c in args.columns if c not in df.columns]
    if missing:
        print(f"[yellow]Warning: Missing columns: {missing}[/yellow]")
        args.columns = [c for c in args.columns if c in df.columns]

    # Keep specified columns
    if args.columns:
        df = df[args.columns]

    # Drop rows duplicate values in 'Image Series ID'
    df = df.drop_duplicates(subset='Image Series ID')
    
    # AAV samples = any Vector Delivery Method that is not blank
    aav_samples_df = df[df['Vector Delivery Method'].notna() & (df['Vector Delivery Method'] != '')]
    aav_samples_df = aav_samples_df.sort_values(by='Image Series ID')

    # Tg samples = Vector Delivery Method is blank
    tg_samples_df = df[df['Vector Delivery Method'].isna() | (df['Vector Delivery Method'] == '')]
    tg_samples_df = tg_samples_df.sort_values(by='Image Series ID')

    print(f"\n[bold green]Found {len(aav_samples_df)} AAV samples and {len(tg_samples_df)} Tg samples.[/bold green]")
    print(f'\nAAV samples:\n{aav_samples_df}\n')
    print(f'\nTg samples:\n{tg_samples_df}\n')

    # Create output directories
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    aav_dir = output_dir / 'AAV_samples'
    tg_dir = output_dir / 'Tg_samples'
    aav_dir.mkdir(parents=True, exist_ok=True)
    tg_dir.mkdir(parents=True, exist_ok=True)

    # Organize AAV samples
    org_samples(aav_samples_df, aav_dir, args.prefix, args.directories)
    
    # Organize Tg samples
    org_samples(tg_samples_df, tg_dir, args.prefix, args.directories)

    verbose_end_msg()
    

if __name__ == "__main__":
    main()
