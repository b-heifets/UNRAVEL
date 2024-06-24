#!/usr/bin/env python3

import argparse
import pandas as pd
import statsmodels.api as sm
from pathlib import Path
from rich import print
from rich.traceback import install
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm

from unravel.cluster_stats.stats import cluster_validation_data_df
from unravel.cluster_stats.stats_table import cluster_summary
from unravel.core.argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(description='Validate clusters based on a 2x2 ANOVA for main effects and interactions', formatter_class=SuppressMetavar)
    parser.add_argument('--factors', help='Names of the two factors and their levels, e.g., Treatment Saline Psilocybin Environment HC EE', nargs=6, required=True)
    parser.add_argument('--valid_criterion', help='Criterion for cluster validity, corresponding to one of the factors or "interaction"', required=True)
    parser.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from fdr.py). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Usage:   ANOVA.py -f1 <group1_prefix> <group2_prefix> -f2 <group3_prefix> <group4_prefix> -vc <valid_criterion> -v

For post hoc comparisons, use the stats.py

Input subdirs: * 
Input files: *_density_data.csv from validate_clusters.py (e.g., in each subdir named after the rev_cluster_index.nii.gz file)    

CSV naming conventions:
    - Condition: first word before '_' in the file name
    - Side: last word before .csv (LH or RH)

Example unilateral inputs in the subdirs:
    - condition1_sample01_<cell|label>_density_data.csv 
    - condition1_sample02_<cell|label>_density_data.csv
    - condition2_sample03_<cell|label>_density_data.csv
    - condition2_sample04_<cell|label>_density_data.csv

Example bilateral inputs (if any file has _LH.csv or _RH.csv, the script will attempt to pool data):
    - condition1_sample01_<cell|label>_density_data_LH.csv
    - condition1_sample01_<cell|label>_density_data_RH.csv
...

Columns in the .csv files:
sample, cluster_ID, <cell_count|label_volume>, cluster_volume, <cell_density|label_density>, ...

Outputs:
    - ./cluster_validation_summary.py and ./subdir/cluster_validation_info/"""
    return parser.parse_args()

# TODO: test script. Test w/ label densities data




def perform_two_way_anova(df, factor1, factor2, response):
    """
    Perform a two-way ANOVA and return the ANOVA table.

    Args:
        df (pd.DataFrame): Data containing the factors and response variable.
        factor1 (str): The first factor (independent variable).
        factor2 (str): The second factor (independent variable).
        response (str): The response variable (dependent variable).

    Returns:
        pd.DataFrame: ANOVA table with the analysis results.
    """
    model = ols(f'{response} ~ C({factor1}) + C({factor2}) + C({factor1}):C({factor2})', data=df).fit()
    anova_table = sm.stats.anova_lm(model, typ=2)
    return anova_table


def main():
    args = parse_args()
    current_dir = Path.cwd()

    # Iterate over all subdirectories in the current working directory
    for subdir in [d for d in current_dir.iterdir() if d.is_dir()]:
        print(f"\nProcessing directory: [bold]{subdir.name}[/]")

        # Load all .csv files in the current subdirectory
        csv_files = list(subdir.glob('*.csv'))
        if not csv_files:
            continue  # Skip directories with no CSV files

        # Load the first .csv file to check for data columns and set the appropriate column names
        first_df = pd.read_csv(csv_files[0])
        
        if 'cell_count' in first_df.columns:
            data_col, data_col_pooled, density_col = 'cell_count', 'pooled_cell_count', 'cell_density'
        elif 'label_volume' in first_df.columns:
            data_col, data_col_pooled, density_col = 'label_volume', 'pooled_label_volume', 'label_density'
        else:
            print("Error: Unrecognized data columns in input files.")
            return

        # Get the total number of clusters
        total_clusters = len(first_df['cluster_ID'].unique())
        
        # Create a results dataframe
        raw_data_df = pd.DataFrame(columns=['condition', 'sample', 'side', 'cluster_ID', data_col, 'cluster_volume', density_col])
        
        # Check if any files contain hemisphere indicators
        has_hemisphere = any('_LH.csv' in str(file.name) or '_RH.csv' in str(file.name) for file in csv_files)

        # Concatenate data from all .csv files and pool the data if hemispheres are present
        data_df = cluster_validation_data_df(density_col, has_hemisphere, csv_files, args.groups, data_col, data_col_pooled)
        if data_df.empty:
            print("No data files match the specified groups. The prefixes of the csv files must match the group names.")
            continue

        # Mapping conditions to factors based on command-line arguments
        data_df = pd.concat([pd.read_csv(f) for f in csv_files])
        data_df['Factor1'] = data_df['condition'].apply(lambda x: args.factors[1] if args.factors[1] in x else args.factors[2])
        data_df['Factor2'] = data_df['condition'].apply(lambda x: args.factors[4] if args.factors[4] in x else args.factors[5])

        # Perform a two-way ANOVA for each cluster
        stats_df = pd.DataFrame()
        for cluster in data_df['cluster_ID'].unique():
            anova_results = perform_two_way_anova(data_df[data_df['cluster_ID'] == cluster], 'Factor1', 'Factor2', density_col)

            # Concat the results to the stats dataframe
            stats_df = pd.concat([stats_df, pd.DataFrame({
                'cluster_ID': cluster,
                'factor': [args.valid_criterion],
                'p-value': anova_results.loc[args.valid_criterion, 'PR(>F)'] if args.valid_criterion in anova_results.index else None
            })], ignore_index=True)
            
        # Add a column for significance levels
        stats_df['significance'] = stats_df['p-value'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')

        if args.verbose:
            print(f'\n{stats_df}\n') 

        # Make output dir
        output_dir = Path(subdir) / '_valid_clusters_stats'
        output_dir.mkdir(exist_ok=True)

        # Save the results to a .csv file
        stats_results_csv = output_dir / f'ANOVA_{args.valid_criterion}_results.csv'
        stats_df.to_csv(stats_results_csv, index=False)

        # Extract the FDR q value from the first csv file (float after 'FDR' or 'q' in the file name)
        first_csv_name = csv_files[0]
        fdr_q = float(str(first_csv_name).split('FDR')[-1].split('q')[-1].split('_')[0])
        
        # Extract the p-value threshold from the specified .txt file
        try:
            p_val_txt = next(Path(subdir).glob('**/*' + args.p_val_txt), None)
            if p_val_txt is None:
                # If no file is found, print an error message and skip further processing for this directory
                print(f"No p-value file found matching '{args.p_val_txt}' in directory {subdir}. Please check the file name and path.")
                import sys ; sys.exit()
            with open(p_val_txt, 'r') as f:
                p_value_thresh = float(f.read())
        except Exception as e:
            # Handle other exceptions that may occur during file opening or reading
            print(f"An error occurred while processing the p-value file: {e}")
            import sys ; sys.exit()

        # Print validation info: 
        print(f"FDR q: [cyan bold]{fdr_q}[/] == p-value threshold: [cyan bold]{p_value_thresh}")
        significant_clusters = stats_df[stats_df['p-value'] < 0.05]['cluster_ID']
        significant_cluster_ids = significant_clusters.unique().tolist()
        significant_cluster_ids_str = ' '.join(map(str, significant_cluster_ids))
        print(f"Valid cluster IDs: [blue bold]{significant_cluster_ids_str}")
        print(f"[default]# of valid / total #: [bright_magenta]{len(significant_cluster_ids)} / {total_clusters}")
        validation_rate = len(significant_cluster_ids) / total_clusters * 100
        print(f"Cluster validation rate: [purple bold]{validation_rate:.2f}%")

        # Save the raw data dataframe as a .csv file
        raw_data_csv_prefix = output_dir / f'raw_data_for_ANOVA_{args.valid_criterion}'
        if has_hemisphere:
            raw_data_df.to_csv(output_dir / f'{raw_data_csv_prefix}_pooled.csv', index=False)
        else: 
            raw_data_df.to_csv(output_dir / f'{raw_data_csv_prefix}.csv', index=False)

        # Save the # of sig. clusters, total clusters, and cluster validation rate to a .txt file
        validation_inf_txt = output_dir / f'cluster_validation_info_ANOVA_{args.valid_criterion}.txt'
        with open(validation_inf_txt, 'w') as f:
            f.write(f"FDR q: {fdr_q} == p-value threshold {p_value_thresh}\n")
            f.write(f"Valid cluster IDs: {significant_cluster_ids_str}\n")
            f.write(f"# of valid / total #: {len(significant_cluster_ids)} / {total_clusters}\n")
            f.write(f"Cluster validation rate: {validation_rate:.2f}%\n")

        # Save the valid cluster IDs to a .txt file
        valid_cluster_IDs = output_dir / f'valid_cluster_IDs_ANOVA_{args.valid_criterion}.txt'
        with open(valid_cluster_IDs, 'w') as f:
            f.write(significant_cluster_ids_str)
        
        # Save cluster validation info for valid_clusters_summary.py
        raw_data_df = pd.DataFrame({
            'FDR q': [fdr_q],
            'P value thresh': [p_value_thresh],
            'Valid clusters': [significant_cluster_ids_str],
            '# of valid clusters': [len(significant_cluster_ids)],
            '# of clusters': [total_clusters],
            'Validation rate': [f"{len(significant_cluster_ids) / total_clusters * 100}%"]
        })
        validation_info_csv = output_dir / f'cluster_validation_info_ANOVA_{args.valid_criterion}.csv'
        raw_data_df.to_csv(validation_info_csv, index=False)

    # Concat all cluster_validation_info.csv files
    cluster_summary(f'cluster_validation_info_ANOVA_{args.valid_criterion}.csv', f'cluster_validation_summary_ANOVA_{args.valid_criterion}.csv')


if __name__ == '__main__':
    install()
    main()