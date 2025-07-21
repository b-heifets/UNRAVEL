#!/usr/bin/env python3

import pandas as pd

def load_tabular_file(file_path):
    """Load a CSV or Excel file into a pandas DataFrame."""
    file_path = str(file_path).lower()
    if file_path.endswith('.csv'):
        return pd.read_csv(file_path), '.csv'
    elif file_path.endswith(('.xls', '.xlsx')):
        return pd.read_excel(file_path), '.xlsx'
    else:
        raise ValueError(f"Unsupported file format: {file_path}")

def save_tabular_file(df, file_path, index=False, verbose=True):
    """Save a pandas DataFrame to a CSV or Excel file."""
    file_path = str(file_path).lower()
    if file_path.endswith('.csv'):
        df.to_csv(file_path, index=index)
    elif file_path.endswith(('.xls', '.xlsx')):
        df.to_excel(file_path, index=index)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")
    if verbose:
        print(f"[green]Data saved to: {file_path}[/green]")