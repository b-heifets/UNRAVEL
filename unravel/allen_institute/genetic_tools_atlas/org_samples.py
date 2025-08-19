#!/usr/bin/env python3

"""
Use ``gta_org_samples`` (``gta_os``) from UNRAVEL to organize GTA data across samples for batch processing.

Prereqs:
    - ``gta_download`` (``gta_dl``) must be run first to download .zarr data at a set resolution.
    - ``io_convert_img`` (``conv``) must be run to convert the .zarr data to TIFF series.

Inputs:
    - `*.zarr` files from ``gta_download`` (``gta_dl``) at a set resolution (e.g., level 3).

Outputs:
    - Root dir: TIFFs/
    - Directories created based on the fluorescent channel (e.g., red, green, dual).
    - Relevant sample directories created in each channel directory (e.g., ID_<Image Series ID>).
    - Sample directories contain 'green' and 'red' directories with TIFF files for each channel.

Note:
    - Key SpecimenMetadata.csv columns: 'Image Series ID' 'Donor Genotype' 'Cargo'
    - Run from GTA_level_3 directory
    
Next steps:
    - ... 

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

COLUMNS = ['Image Series ID', 'Donor Genotype', 'Cargo']

# Logic determined when there was 3902 GTA STPT records (as of 2025-08-19):
CARGO_MAP = { 
    'NA': 'USE Tg LOGIC',
    'iCre(R297T)': 'green if Ai193 is in "Donor Genotype" else red',
    'SYFP2': 'green',
    'iCre': 'green if Ai193 is in "Donor Genotype" else red',
    'FlpO': 'red',
    'dTomato': 'red',
    'jGCaMP8m': 'green',
    'SYFP2 | iCre(R297T)': 'green',
    'iCre(R297T) | EGFP': 'dual',
    'SYFP2 | mScarlet': 'dual',
    'iCre(R297T) | SYFP2': 'green',
    'ChR2(H134R) | dTomato | EYFP': 'dual',
    'EYFP': 'green',
    'tdTomato | SYFP2': 'dual',
    'iCre | FlpO': 'dual',
    'FlpO | iCre': 'dual',
    'iCre(R297T) | tdTomato': 'red',
    'EGFP | iCre(R297T)': 'dual',
    'EYFP | ChR2(H134R)': 'green',
    'CreN': 'red',
    'tdTomato | iCre(R297T)': 'red',
    'mScarlet | SYFP2': 'dual',
    'ChR2(H134R) | EYFP | dTomato': 'dual',
    'SYFP2 | tdTomato': 'dual'
}

# If 'Cargo' is 'NA', use Tg logic (Check 'Donor Genotype' for the presence of these list items to determine the channel [green, red, or dual]):
GREEN_TG =  ['GFP', 'Ai210', 'Ai195', 'RCE-FRT']
RED_TG = ['tdTomato', 'Ai223', 'Ai65F']

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-d', '--directories', help='Space-separated list of tif directory names to organize. Default: "red green"', default=['red', 'green'], nargs='*', action=SM)
    opts.add_argument('-i', '--input', help='path/SpecimenMetadata.csv. Default: unravel/allen_institute/genetic_tools_atlas/SpecimenMetadata_subset.csv', default=None, action=SM)
    opts.add_argument('-o', '--output_dir', help='Output directory for organized samples', default='TIFFs', action=SM)
    opts.add_argument('-p', '--prefix', help='Prefix for sample directories (useful for batch processing). Default: "ID_"', default='ID_', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def org_samples(df, target_dir, prefix, tif_dirs):
    """
    Organize samples into directories based on the SpecimenMetadata DataFrame.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame containing 'Image Series ID' with the sample IDs to organize.
    target_dir : Path
        Directory where the sample directories will be created.
    prefix : str
        Prefix for sample directories.
    tif_dirs : list of str
        List of TIFF directory names to organize (e.g., ['red', 'green']).
    """
    for _, row in df.iterrows():
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
                    if not any(p for p in tif_dir.iterdir() if not p.name.startswith('.')):
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

    print(f"\n[bold green]SpecimenMetadata.csv file:\n  [/bold green]{input_path}\n")

    if not input_path.is_file():
        print(f"[bold red]SpecimenMetadata file not found: [/bold red]{input_path}")
        return

    df = pd.read_csv(input_path, usecols=COLUMNS)

    # Drop rows duplicate values in 'Image Series ID'
    df = df.drop_duplicates(subset='Image Series ID')

    # Add a 'Channel' column based on 'Cargo' and 'Donor Genotype'
    df['Channel'] = df['Cargo'].apply(lambda x: CARGO_MAP.get(x, 'NA')) # Set 'Channel' using 'Cargo' as the key

    # Handle conditional logic for 'Channel'
    for i in ['iCre(R297T)', 'iCre']:
        df.loc[df['Cargo'] == i, 'Channel'] = df.apply(
            lambda row: 'green' if 'Ai193' in row['Donor Genotype'] else 'red',
            axis=1
        )

    # If 'Cargo' is 'NA', use Tg logic to determine the channel
    df.loc[df['Channel'] == 'NA', 'Channel'] = df.apply(
        lambda row: 'green' if any(g in row['Donor Genotype'] for g in GREEN_TG) else
                     ('red' if any(r in row['Donor Genotype'] for r in RED_TG) else 'dual'),
        axis=1
    )

    # Print rows with 'Channel' as 'NA' (if any)
    na_channel_rows = df[df['Channel'] == 'NA']
    if not na_channel_rows.empty:
        print(f"[bold yellow]Warning: Found {len(na_channel_rows)} rows with 'Channel' as 'NA'. These will be skipped.[/bold yellow]")
        print(na_channel_rows)

    # Create a df for green, red, and dual channels with the 'Image Series ID' column
    green_df = df[df['Channel'] == 'green'][['Image Series ID']].sort_values(by='Image Series ID')
    red_df = df[df['Channel'] == 'red'][['Image Series ID']].sort_values(by='Image Series ID')
    dual_df = df[df['Channel'] == 'dual'][['Image Series ID']].sort_values(by='Image Series ID')

    # Create output directories
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    green_dir = output_dir / 'green'
    red_dir = output_dir / 'red'
    dual_dir = output_dir / 'dual'
    green_dir.mkdir(parents=True, exist_ok=True)
    red_dir.mkdir(parents=True, exist_ok=True)
    dual_dir.mkdir(parents=True, exist_ok=True)

    # Organize green samples
    org_samples(green_df, green_dir, args.prefix, args.directories)

    # Organize red samples
    org_samples(red_df, red_dir, args.prefix, args.directories)

    # Organize dual samples
    org_samples(dual_df, dual_dir, args.prefix, args.directories)

    verbose_end_msg()
    

if __name__ == "__main__":
    main()
