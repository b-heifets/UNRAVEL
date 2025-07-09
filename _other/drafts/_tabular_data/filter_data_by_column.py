#!/usr/bin/env python3

"""

This script is useful for filtering tabular data to retain a subset of rows based on the values in a specific column. 
For example, you can keep data for valid clusters.

"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="One or more CSV/XLSX file paths or glob patterns (space-separated), e.g., 'data/*.csv'", required=True, nargs='*', action=SM)
    reqs.add_argument('-col', '--column', help="Column to filter", required=True, action=SM)
    reqs.add_argument('-vals', '--values', nargs='*', help="Values to filter by", required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-od', '--output_dir', help="Directory to save filtered files", default="filtered_files", action=SM)
    opts.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()

# TODO complete __doc__ string and add to the main repo

def filter_file(file_path, column, values, output_dir):
    """
    Filter a CSV or XLSX file based on column values and save the filtered data to an output directory.

    Parameters:
    -----------
    file_path : str
        Path to the input file (CSV or XLSX).
    
    column : str
        Column name to filter by.

    values : list
        List of values to filter by.

    output_dir : str
        Path to the output directory to save the filtered file.
    """
    # Determine file extension and read the file accordingly
    if file_path.lower().endswith('.csv'):
        df = pd.read_csv(file_path)
        file_extension = ".csv"
    elif file_path.lower().endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file_path)
        file_extension = ".xlsx"
    else:
        print(f"[bold red]Unsupported file format: {file_path}[/bold red]")
        return

    # Convert the column and values to strings for consistent comparison
    df[column] = df[column].astype(str)
    values = [str(value) for value in values]

    # Filter the dataframe based on the column and values
    filtered_df = df[df[column].isin(values)]
    
    # Save the filtered dataframe to the output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / str(Path(file_path).name).replace(file_extension, f"_filtered{file_extension}")
    
    if file_extension == ".csv":
        filtered_df.to_csv(output_path, index=False)
    else:
        filtered_df.to_excel(output_path, index=False)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    file_paths = match_files(args.input)
    for file_path in file_paths:


        # Skip temporary files that start with ~
        if Path(file_path).name.startswith("~"):
            continue
        
        filter_file(file_path, args.column, args.values, args.output_dir)

    verbose_end_msg()

if __name__ == '__main__':
    main()
