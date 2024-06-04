#!/usr/bin/env python3

import argparse
import os
import pandas as pd
from termcolor import colored

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.utils import print_cmd

def parse_args():
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(description='Merge densities and sex information from CSVs.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input_csv', help='CSV with cell or fiber densities.', action=SM)
    parser.add_argument('-s', '--sex_info_csv', help='CSV with "Samples" and "Sex" columns.', action=SM)
    return parser.parse_args()

def add_sexes_to_input_csv(input_csv, sex_info_csv):
    """
    Merges the given input csv and sex_info csv based on the Samples column to add sex information to the input csv.
    Ensures the merged DataFrame has the desired order of columns.
    """
    densities_df = pd.read_csv(input_csv)
    sample_info_df = pd.read_csv(sex_info_csv)

    if len(densities_df) != len(sample_info_df):
        raise ValueError(colored(f"The two dataframes have different numbers of rows ({len(densities_df)} vs {len(sample_info_df)})", 'red'))

    # Reordering for consistent sample IDs
    densities_df.set_index('Samples', inplace=True)
    sample_info_df.set_index('Samples', inplace=True)
    sample_info_df = sample_info_df.reindex(densities_df.index)
    densities_df.reset_index(inplace=True)
    sample_info_df.reset_index(inplace=True)

    if not (densities_df['Samples'] == sample_info_df['Samples']).all():
        raise ValueError(colored("The two dataframes have different sample IDs", 'red'))

    merged_df = pd.merge(densities_df, sample_info_df[['Samples', 'Sex']], on='Samples', how='left')

    cluster_columns = [col for col in densities_df if col.startswith('Cluster')]
    desired_columns = ['Samples', 'Sex', 'Conditions'] + cluster_columns
    merged_df = merged_df[desired_columns]

    return merged_df

def main():
    args = parse_args()
    print_cmd()

    merged_df = add_sexes_to_input_csv(args.input_csv, args.sex_info_csv)
    output = f"{os.path.splitext(args.input_csv)[0]}_w_sexes.csv"
    merged_df.to_csv(output, index=False)

if __name__ == '__main__':
    main()

# Daniel Rijsketic 08/17/2023 (Heifets lab)