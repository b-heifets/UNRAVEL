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
    gta_os [-d red green] [-i "path/to/SpecimenMetadata.csv"] [-col col1 col2 ...] [-o output_dir] [-p sample_prefix] [-v]
"""

import shutil
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

COLUMNS = ['Image Series ID', 'Vector Delivery Method']

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-d', '--directories', help='Space-separated list of tif directory names to organize. Default: "red green"', default=['red', 'green'], nargs='*', action=SM)
    opts.add_argument('-i', '--input', help='path/SpecimenMetadata.csv. Default: SpecimenMetadata_subset.csv in unravel/allen_institute/genetic_tools_atlas', default=None, action=SM)
    opts.add_argument('-col', '--columns', help='CSV columns to keep. See notes for default columns.', nargs='*', default=COLUMNS, action=SM)
    opts.add_argument('-o', '--output_dir', help='Output directory for organized samples', default='TIFFs', action=SM)
    opts.add_argument('-p', '--prefix', help='Prefix for sample directories (useful for batch processing). Default: "ID_"', default='ID_', action=SM)

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
        List of TIFF directory names to organize (e.g., ['red', 'green']).
    """
    for _, row in aav_samples_df.iterrows():
        series_id = row['Image Series ID']
        sample_dir = target_dir / f'{prefix}{series_id}'

        for dir in tif_dirs:
            tif_dir = Path(dir) / str(series_id)
            if tif_dir.is_dir():
                dest = sample_dir / str(dir)
                dest.mkdir(parents=True, exist_ok=True)

                # Move all TIFFs from tif_dir to dest
                for item in tif_dir.iterdir():
                    if item.suffix == '.tif':
                        shutil.move(str(item), str(dest))

                # Remove the tif_dir if empty
                try:
                    tif_dir.rmdir()
                except OSError:
                    print(f'Warning: {tif_dir} not empty or failed to remove.')

    # Remove parent directories ('red', 'green') if they are now empty
    for dir in tif_dirs:
        tif_dir = Path(dir)
        if not tif_dir.exists():
            continue  # It's already deleted — no warning needed
        try:
            if not any(p for p in tif_dir.iterdir() if not p.name.startswith('.')):
                tif_dir.rmdir()
        except Exception as e:
            print(f'Warning: {tif_dir} could not be removed ({e})')


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.input is None:
        input_path = Path(__file__).parent / 'SpecimenMetadata_subset.csv'
    else:
        input_path = Path(args.input)

    print(f"[bold green]Using input file:[/bold green] {input_path}")

    if not input_path.is_file():
        print(f"[bold red]Input file not found:[/bold red] {input_path}")
        return

    df = pd.read_csv(input_path, usecols=args.columns)

    # Drop rows duplicate values in 'Image Series ID'
    df = df.drop_duplicates(subset='Image Series ID')
    
    # AAV samples = any Vector Delivery Method that is not blank
    aav_samples_df = df[df['Vector Delivery Method'].notna() & (df['Vector Delivery Method'] != '')]
    aav_samples_df = aav_samples_df.sort_values(by='Image Series ID')

    # Tg samples = Vector Delivery Method is blank
    tg_samples_df = df[df['Vector Delivery Method'].isna() | (df['Vector Delivery Method'] == '')]
    tg_samples_df = tg_samples_df.sort_values(by='Image Series ID')

    # Create output directories
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    aav_dir = output_dir / 'AAV'
    tg_dir = output_dir / 'Tg'
    aav_dir.mkdir(parents=True, exist_ok=True)
    tg_dir.mkdir(parents=True, exist_ok=True)

    # Organize AAV samples
    org_samples(aav_samples_df, aav_dir, args.prefix, args.directories)
    
    # Organize Tg samples
    org_samples(tg_samples_df, tg_dir, args.prefix, args.directories)

    verbose_end_msg()
    

if __name__ == "__main__":
    main()
