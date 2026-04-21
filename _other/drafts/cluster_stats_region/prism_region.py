#!/usr/bin/env python3

"""
Use ``cstats_prism`` (``prism``) from UNRAVEL to organize data for clusters for plotting in Prism.

Inputs:
    `*`.csv from ``cstats_org_data`` / ``cstats_validation`` outputs in the working dir

CSV naming conventions:
    - Condition: first word before '_' in the file name (use ``utils_prepend`` if needed)
    - Sample: second word in file name

Example unilateral inputs:
    - condition1_sample01_<metric>_data.csv
    - condition1_sample02_<metric>_data.csv
    - condition2_sample03_<metric>_data.csv
    - condition2_sample04_<metric>_data.csv

Example bilateral inputs (if any file has _LH.csv or _RH.csv, the command will attempt to pool data):
    - condition1_sample01_<metric>_data_LH.csv
    - condition1_sample01_<metric>_data_RH.csv

Columns in the input .csv files:
    sample, cluster_ID, metric, value, value_type, support, support_type, aggregation_method, cluster_volume, ...

Outputs:
    - Outputs saved in ./_prism/
    - Cluster order follows -ids order
    - <metric>_summary.csv
    - [<metric>_summary_for_valid_clusters.csv]
    - [<metric>_summary_across_clusters.csv]
    - [cluster_volume_summary.csv]

Note:
    - cstats_table saves valid_clusters_dir/valid_cluster_IDs_sorted_by_anatomy.txt
    - Hemisphere suffix usage must be consistent across files (all _LH/_RH or none).

Usage:
------
    cstats_prism [-ids 1 2 3] [-p /path/to/csv/files/from/cstats_validation] [-v]
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.cluster_stats.cstats import detect_metric_schema
from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-ids', '--valid_cluster_ids', help='Space-separated list of valid cluster IDs to include in the summary.', nargs='*', type=int, default=None, action=SM)
    opts.add_argument('-p', '--path', help='Path to the directory containing the CSV files from ``cstats_validation``. Default: current directory', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


# TODO: Address this warning:
# /usr/local/UNRAVEL_dev/unravel/cluster_stats/prism.py:190: PerformanceWarning: dropping on a non-lexsorted multi-index without a level parameter may impact performance.
# density_col_summary_df_sum = density_col_summary_df_sum.drop('cluster_ID').reset_index().T
# TODO: Simplify and improve handling when data is missing or empty 
# TODO: Restore support for processing CSVs from cstats_mean_IF with generic schema (also need to handle pooling and excluded hemispheres). 

def sort_samples(sample_names):
    # Extract the numeric part of the sample names and sort by it
    return sorted(sample_names, key=lambda x: int(''.join(filter(str.isdigit, x))))

def pool_sample_rows(dfs, metric_name, value_col, support_col, aggregation_method):
    """Pool LH/RH data for one sample if both sides are present; otherwise use available side only."""
    combined = pd.concat(dfs, ignore_index=True)

    if len(dfs) == 1:
        return combined[['sample', 'cluster_ID', value_col]]

    if aggregation_method == 'recompute_from_support_and_volume':
        pooled = (
            combined.groupby(['sample', 'cluster_ID'], as_index=False)
            .agg(
                support_sum=(support_col, 'sum'),
                cluster_volume_sum=('cluster_volume', 'sum')
            )
        )
        pooled[value_col] = pooled['support_sum'] / pooled['cluster_volume_sum']
        if metric_name == 'label_density':
            pooled[value_col] *= 100
        return pooled[['sample', 'cluster_ID', value_col]]

    elif aggregation_method == 'weighted_mean_by_support':
        def weighted_mean(g):
            support_sum = g[support_col].sum()
            if support_sum == 0 or pd.isna(support_sum):
                return np.nan
            return np.average(g[value_col], weights=g[support_col])

        pooled = (
            combined.groupby(['sample', 'cluster_ID'])
            .apply(lambda g: pd.Series({value_col: weighted_mean(g)}))
            .reset_index()
        )
        return pooled[['sample', 'cluster_ID', value_col]]

    else:
        raise ValueError(
            f"Unsupported aggregation_method: {aggregation_method}. "
            "Expected 'recompute_from_support_and_volume' or 'weighted_mean_by_support'."
        )

def generate_summary_table(csv_files, schema, field='value'):
    """Generate a Prism summary table for the requested field.

    field can be:
        - 'value'
        - 'support'
        - 'cluster_volume'
    """
    metric_name = schema['metric_name']
    value_col = schema['value_col']
    support_col = schema['support_col']
    aggregation_method = schema['aggregation_method']
    schema_type = schema['schema_type']

    data_by_condition = {}
    has_hemisphere = any(str(f).endswith('_LH.csv') or str(f).endswith('_RH.csv') for f in csv_files)

    if has_hemisphere:
        by_key = {}
        for f in csv_files:
            name = Path(f).name
            if str(name).endswith('_LH.csv') or str(name).endswith('_RH.csv'):
                key = str(name).replace('_LH.csv', '').replace('_RH.csv', '')
                by_key.setdefault(key, []).append(f)

        for key, files in by_key.items():
            parts = key.split('_')
            condition = parts[0]
            sample = parts[1]

            dfs = []
            for f in files:
                df = pd.read_csv(f)

                if schema_type == 'generic':
                    if field == 'value':
                        cols = ['sample', 'cluster_ID', 'value', 'support', 'cluster_volume']
                    elif field == 'support':
                        cols = ['sample', 'cluster_ID', 'support']
                    elif field == 'cluster_volume':
                        cols = ['sample', 'cluster_ID', 'cluster_volume']
                    else:
                        raise ValueError(f"Unsupported field: {field}")

                    dfs.append(df[cols].copy())

                else:
                    if field == 'value':
                        cols = ['sample', 'cluster_ID', value_col]
                        if support_col is not None and 'cluster_volume' in df.columns:
                            cols += [support_col, 'cluster_volume']
                    elif field == 'support' and support_col is not None:
                        cols = ['sample', 'cluster_ID', support_col]
                    elif field == 'cluster_volume' and 'cluster_volume' in df.columns:
                        cols = ['sample', 'cluster_ID', 'cluster_volume']
                    else:
                        continue

                    dfs.append(df[cols].copy())

            if not dfs:
                continue

            if field == 'value':
                if schema_type == 'generic':
                    pooled_df = pool_sample_rows(
                        dfs=dfs,
                        metric_name=metric_name,
                        value_col='value',
                        support_col='support',
                        aggregation_method=aggregation_method
                    )
                    data_column_name = 'value'
                else:
                    if len(dfs) == 1:
                        pooled_df = dfs[0][['sample', 'cluster_ID', value_col]].copy()
                    else:
                        pooled_df = pool_sample_rows(
                            dfs=dfs,
                            metric_name=metric_name,
                            value_col=value_col,
                            support_col=support_col,
                            aggregation_method=aggregation_method
                        )
                    data_column_name = value_col

            elif field == 'support':
                combined = pd.concat(dfs, ignore_index=True)
                col = 'support' if schema_type == 'generic' else support_col
                pooled_df = (
                    combined.groupby(['sample', 'cluster_ID'], as_index=False)
                    .agg(**{col: (col, 'sum')})
                )
                data_column_name = col

            elif field == 'cluster_volume':
                combined = pd.concat(dfs, ignore_index=True)
                pooled_df = (
                    combined.groupby(['sample', 'cluster_ID'], as_index=False)
                    .agg(cluster_volume=('cluster_volume', 'sum'))
                )
                data_column_name = 'cluster_volume'

            else:
                raise ValueError(f"Unsupported field: {field}")

            pooled_df.set_index('cluster_ID', inplace=True)
            pooled_df = pooled_df[[data_column_name]]
            pooled_df.rename(columns={data_column_name: sample}, inplace=True)

            if condition not in data_by_condition:
                data_by_condition[condition] = pooled_df
            else:
                data_by_condition[condition] = pd.concat([data_by_condition[condition], pooled_df], axis=1)

    else:
        for file in csv_files:
            parts = Path(file).name.split('_')
            condition = parts[0]
            sample = parts[1]
            df = pd.read_csv(file)

            if schema_type == 'generic':
                if field == 'value':
                    col = 'value'
                elif field == 'support':
                    col = 'support'
                elif field == 'cluster_volume':
                    col = 'cluster_volume'
                else:
                    raise ValueError(f"Unsupported field: {field}")
            else:
                if field == 'value':
                    col = value_col
                elif field == 'support':
                    col = support_col
                elif field == 'cluster_volume':
                    col = 'cluster_volume'
                else:
                    raise ValueError(f"Unsupported field: {field}")

            if col is None or col not in df.columns:
                continue

            df = df[['sample', 'cluster_ID', col]].copy()
            if df.empty:
                continue

            df.set_index('cluster_ID', inplace=True)
            df = df[[col]]
            df.rename(columns={col: sample}, inplace=True)

            if condition not in data_by_condition:
                data_by_condition[condition] = df
            else:
                data_by_condition[condition] = pd.concat([data_by_condition[condition], df], axis=1)

    for condition in data_by_condition:
        data_by_condition[condition] = data_by_condition[condition][sort_samples(data_by_condition[condition].columns)]

    all_conditions_df = pd.concat(data_by_condition.values(), axis=1, keys=data_by_condition.keys())
    all_conditions_df.reset_index(inplace=True)

    return all_conditions_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    path = Path(args.path) if args.path else Path.cwd()
    csv_files = match_files('*.csv', base_path=path)

    # Print CSVs in the base path if verbose is enabled
    if args.verbose:
        print(f'\n[bold]CSVs in {path} to process (the first word defines the groups): \n')
        for filename in csv_files:
            print(f'    {filename.name}')
        print()

    first_df = pd.read_csv(csv_files[0])

    try:
        schema = detect_metric_schema(first_df)
    except ValueError as e:
        print(f"Error: {e}")
        return

    metric_name = schema['metric_name']
    value_col = schema['value_col']
    support_col = schema['support_col']
    aggregation_method = schema['aggregation_method']

    # Generate a summary table for the main metric column (e.g., cell_count, label_volume, mean_IF_intensity)
    value_summary_df = generate_summary_table(csv_files, schema, field='value')

    if support_col is not None:
        support_summary_df = generate_summary_table(csv_files, schema, field='support')
    else:
        support_summary_df = None

    if 'cluster_volume' in first_df.columns:
        cluster_volume_summary_df = generate_summary_table(csv_files, schema, field='cluster_volume')
    else:
        cluster_volume_summary_df = None
    
    density_like_summary_df = None
    density_like_summary_df_sum = None

    if metric_name in ('cell_density', 'label_density') and support_summary_df is not None and cluster_volume_summary_df is not None:
        cluster_ids = support_summary_df.iloc[:, 0]
        density_values = support_summary_df.iloc[:, 1:] / cluster_volume_summary_df.iloc[:, 1:]

        if metric_name == 'label_density':
            density_values = density_values * 100

        density_like_summary_df = pd.concat([cluster_ids, density_values], axis=1)

    # Save the summary tables to .csv files
    output_dir = path / '_prism'
    Path(output_dir).mkdir(exist_ok=True)
    value_summary_df.to_csv(output_dir / f'{metric_name}_summary.csv', index=False)

    if support_summary_df is not None:
        support_name = support_col if support_col is not None else 'support'
        support_summary_df.to_csv(output_dir / f'{support_name}_summary.csv', index=False)

    if cluster_volume_summary_df is not None:
        cluster_volume_summary_df.to_csv(output_dir / 'cluster_volume_summary.csv', index=False)

    # Exclude clusters that are not in the list of valid clusters
    if args.valid_cluster_ids is not None:
        order_map = {cluster: i for i, cluster in enumerate(args.valid_cluster_ids)}

        value_summary_df = value_summary_df[value_summary_df['cluster_ID'].isin(args.valid_cluster_ids)]
        value_summary_df = value_summary_df.sort_values(by='cluster_ID', key=lambda x: x.map(order_map))

        if support_summary_df is not None:
            support_summary_df = support_summary_df[support_summary_df['cluster_ID'].isin(args.valid_cluster_ids)]
            support_summary_df = support_summary_df.sort_values(by='cluster_ID', key=lambda x: x.map(order_map))

        if cluster_volume_summary_df is not None:
            cluster_volume_summary_df = cluster_volume_summary_df[cluster_volume_summary_df['cluster_ID'].isin(args.valid_cluster_ids)]
            cluster_volume_summary_df = cluster_volume_summary_df.sort_values(by='cluster_ID', key=lambda x: x.map(order_map))

        if density_like_summary_df is not None:
            density_like_summary_df = density_like_summary_df[density_like_summary_df['cluster_ID'].isin(args.valid_cluster_ids)]
            density_like_summary_df = density_like_summary_df.sort_values(by='cluster_ID', key=lambda x: x.map(order_map))

    if cluster_volume_summary_df is not None:
        cluster_volume_summary_df_sum = cluster_volume_summary_df.sum(numeric_only=False)
    else:
        cluster_volume_summary_df_sum = None

    if support_summary_df is not None:
        support_summary_df_sum = support_summary_df.sum(numeric_only=False)
    else:
        support_summary_df_sum = None

    if density_like_summary_df is not None and support_summary_df_sum is not None and cluster_volume_summary_df_sum is not None:
        density_like_summary_df_sum = support_summary_df_sum / cluster_volume_summary_df_sum
        multi_index = support_summary_df.columns
        density_like_summary_df_sum.index = multi_index
        density_like_summary_df_sum = density_like_summary_df_sum.drop('cluster_ID').reset_index().T

    # Save filtered or across-cluster outputs
    if args.valid_cluster_ids is not None:
        value_summary_df.to_csv(output_dir / f'{metric_name}_summary_for_valid_clusters.csv', index=False)

        if support_summary_df is not None:
            support_name = support_col if support_col is not None else 'support'
            support_summary_df.to_csv(output_dir / f'{support_name}_summary_for_valid_clusters.csv', index=False)

        if cluster_volume_summary_df is not None:
            cluster_volume_summary_df.to_csv(output_dir / 'valid_cluster_volume_summary.csv', index=False)

        if density_like_summary_df is not None:
            density_like_summary_df.to_csv(output_dir / f'{metric_name}_recomputed_summary_for_valid_clusters.csv', index=False)

        if density_like_summary_df_sum is not None:
            density_like_summary_df_sum.to_csv(output_dir / f'{metric_name}_summary_across_valid_clusters.csv', index=False)

    else:
        if density_like_summary_df_sum is not None:
            density_like_summary_df_sum.to_csv(output_dir / f'{metric_name}_summary_across_clusters.csv', index=False)

    if args.verbose:
        print(f"\n    Saved CSVs for plotting with Prism to[bright_magenta]{output_dir}")

    verbose_end_msg()


if __name__ == '__main__':
    main()