#!/usr/bin/env python3

import pandas as pd
from pathlib import Path
from rich import print

def load_tabular_file(file_path):
    """Load a CSV or Excel file into a pandas DataFrame."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == '.csv':
        return pd.read_csv(file_path), '.csv'
    elif suffix in ('.xls', '.xlsx'):
        return pd.read_excel(file_path), '.xlsx'
    else:
        raise ValueError(f"Unsupported file format: {file_path}")

def save_tabular_file(df, file_path, index=False, verbose=True):
    """Save a pandas DataFrame to a CSV or Excel file."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == '.csv':
        df.to_csv(file_path, index=index)
    elif suffix in ('.xls', '.xlsx'):
        df.to_excel(file_path, index=index)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")
    
    if verbose:
        print(f"[green]Data saved to: {file_path}[/green]")