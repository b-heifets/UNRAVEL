#!/usr/bin/env python3

"""
Use ``rstats_mean_IF_summary`` (``rmis``) from UNRAVEL to output plots of mean IF intensities for each region intensity ID.

Prereqs:
    - Generate CSV inputs withs ``rstats_IF_mean`` or ``rstats_IF_mean_in_seg``
    - After ``rstats_IF_mean_in_seg``, aggregate CSV inputs with ``utils_agg_files``
    - If needed, add conditions to input CSV file names: ``utils_prepend`` -sk $SAMPLE_KEY -f

Inputs: 
    - `*`.csv in the working dir with these columns: 'Region_Intensity', 'Mean_IF_Intensity'

Outputs:
    - regional_mean_IF_summary/region_<region_id>_<region_abbr>.pdf for each region
    - regional_mean_IF_summary/regional_mean_IF_summary_<test>.csv
    - A prefix '_' marks plots with FDR-significant differences at --q (default: 0.05).

Note:
    - The first word of the csv inputs is used for the the group names (e.g. Control from Control_sample01_cFos_rb4_atlas_space_z.csv)
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020__regionID_side_IDpath_region_abbr.csv
    - Alternatively, use CCFv3-2017__regionID_side_IDpath_region_abbr.csv or provide a custom CSV with the same columns.
    - Benjamini-Hochberg FDR correction pools all finite p values across all processed regions and group comparisons in this run.
    - For t-tests, FDR uses raw p values; for Tukey/Dunnett, it uses their within-region adjusted p values (an additional conservative correction).
    - BH assumes independent or suitably positively dependent tests; it does not guarantee control under arbitrary dependence.
    - Original p values and significance are retained; p-fdr, reject_fdr, significance_fdr, and fdr_q report the correction.
    - Plot stars use p-fdr (<0.0001: ****, <0.001: ***, <0.01: **, otherwise * when rejected at q).
    - Non-finite p values remain untested (NaN p-fdr, False reject_fdr).
    - The look up table (LUT) csv has these columns: 'Region_ID', 'Side', 'Name', 'Abbr'

Usage for t-tests:
------------------
    rstats_mean_IF_summary --order Control Treatment --labels Control Treatment -t ttest [-alt two-sided] [--lut CCFv3-2020__regionID_side_IDpath_region_abbr.csv] [-v]

Usage for Tukey's tests w/ reordering and renaming of conditions:
-----------------------------------------------------------------
    rstats_mean_IF_summary --order group3 group2 group1 --labels Group_3 Group_2 Group_1 [--lut CCFv3-2020__regionID_side_IDpath_region_abbr.csv] [-v]

Usage with a custom atlas:
--------------------------
    atlas=path/custom_atlas.nii.gz ; rstats_mean_IF_summary --region_ids $(img_unique -i $atlas) --order group2 group1 --labels Group_2 Group_1 -t ttest [-alt two-sided] [--lut CCFv3-2020__regionID_side_IDpath_region_abbr.csv] [-v]
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import textwrap
from rich import print
from rich.traceback import install
from pathlib import Path
from scipy.stats import ttest_ind, dunnett
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.multitest import multipletests

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('--order', nargs='*', help='Group Order for plotting (must match 1st word of CSVs)', action=SM)
    reqs.add_argument('--labels', nargs='*', help='Group Labels in same order', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-t', '--test', help='Choose between "tukey", "dunnett", and "ttest" post-hoc tests. Default: ttest or tukey', default=None, choices=['tukey', 'dunnett', 'ttest'], action=SM)
    opts.add_argument('-alt', "--alternate", help="Number of tails and direction for Dunnett's test {'two-sided', 'less' (means < ctrl), 'greater'}. Default: two-sided", default='two-sided', action=SM)
    opts.add_argument('--region_ids', nargs='*', type=int, help='List of region intensity IDs (Default: process all regions from the lut CSV)', action=SM)
    opts.add_argument('-l', '--lut', help='LUT csv name (in unravel/core/csvs/). Default: CCFv3-2020__regionID_side_IDpath_region_abbr.csv', default="CCFv3-2020__regionID_side_IDpath_region_abbr.csv", action=SM)
    opts.add_argument('-q', '--q', type=float, default=0.05, help='FDR threshold across all regions and comparisons; must be between 0 and 1. Default: 0.05', action=SM)
    opts.add_argument('-s', '--skip_plots', help='Only write the summary CSV; do not generate PDF plots.', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    args = parser.parse_args()
    if not 0 < args.q < 1:
        parser.error('--q must be strictly between 0 and 1.')
    return args

# TODO: Make symbols transparent. Add option to pass in symbol colors for each group. Add ABA coloring to plots. 
# TODO: CSVs are loaded for each region. It would be more efficient to load them once for processing all regions. 
# TODO: Update coloring of plots to match ABA colors (i.e., use code from rstats_summary.py)


# Set Arial as the font
mpl.rcParams['font.family'] = 'Arial'

def load_data(region_id):
    data = []
    
    # Load all CSVs in the directory
    for filename in os.listdir():
        if filename.endswith('.csv'):
            group_name = filename.split("_")[0]
            df = pd.read_csv(filename)

            # Filter by the region ID
            mean_intensity = df[df["Region_Intensity"] == region_id]["Mean_IF_Intensity"].values

            if len(mean_intensity) > 0:
                data.append({
                    'group': group_name,
                    'mean_intensity': mean_intensity[0]
                })
    
    if data:
        return pd.DataFrame(data)
    else:
        raise ValueError(f"    [red1]No data found for region ID {region_id}")

def get_max_region_id_from_csvs():
    """Retrieve the maximum Region_Intensity from all input CSVs."""
    max_region_id = -1
    for filename in os.listdir():
        if filename.endswith('.csv'):
            df = pd.read_csv(filename)
            max_id_in_file = df["Region_Intensity"].max()
            if max_id_in_file > max_region_id:
                max_region_id = max_id_in_file
    return max_region_id

def get_region_details(region_id, csv_path):
    region_df = pd.read_csv(csv_path)
    region_row = region_df[region_df["Region_ID"] == region_id].iloc[0]
    return region_row["Region"], region_row["Abbr"]

def get_all_region_ids(csv_path):
    """Retrieve all region IDs from the provided CSV."""
    region_df = pd.read_csv(csv_path)
    return region_df["Region_ID"].tolist()

def filter_region_ids(region_ids, max_region_id):
    """Filter region IDs to be within the maximum region ID from the CSVs."""
    return [region_id for region_id in region_ids if region_id <= max_region_id]

def remove_zero_intensity_regions(region_ids):
    """Remove regions with Mean_IF_Intensity of 0 across all input CSVs."""
    valid_region_ids = []
    for region_id in region_ids:
        all_zero = True
        for filename in os.listdir():
            if filename.endswith('.csv'):
                df = pd.read_csv(filename)
                mean_intensity = df[df["Region_Intensity"] == region_id]["Mean_IF_Intensity"].values
                if len(mean_intensity) > 0 and mean_intensity[0] != 0:
                    all_zero = False
                    break
        if not all_zero:
            valid_region_ids.append(region_id)
    return valid_region_ids

def perform_t_tests(df, order):
    """Perform t-tests between groups in the DataFrame."""
    comparisons = []
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            group1, group2 = order[i], order[j]
            data1 = df[df['group'] == group1]['mean_intensity']
            data2 = df[df['group'] == group2]['mean_intensity']
            t_stat, p_value = ttest_ind(data1, data2)
            comparisons.append({
                'group1': group1,
                'group2': group2,
                'statistic': t_stat,
                'p-value': p_value,
                'reject': p_value < 0.05,
            })
    return pd.DataFrame(comparisons)


def add_group_summary_columns(test_df, df):
    """Add n, means, and mean differences to the stats table."""
    group_stats = (
        df.groupby('group', observed=True)['mean_intensity']
        .agg(['count', 'mean'])
    )

    rows = []
    for _, row in test_df.iterrows():
        row = row.to_dict()
        group1 = row['group1']
        group2 = row['group2']

        row['n_group1'] = int(group_stats.loc[group1, 'count'])
        row['n_group2'] = int(group_stats.loc[group2, 'count'])
        row['mean_group1'] = float(group_stats.loc[group1, 'mean'])
        row['mean_group2'] = float(group_stats.loc[group2, 'mean'])
        row['diff_group2_minus_group1'] = row['mean_group2'] - row['mean_group1']

        rows.append(row)

    return pd.DataFrame(rows)


def run_stats(df, order, test_type, alt):
    """Run the selected statistical test."""
    if test_type == 'tukey':
        test_results = pairwise_tukeyhsd(df['mean_intensity'], df['group'])
        summary = test_results.summary()
        test_df = pd.DataFrame(summary.data[1:], columns=summary.data[0])
        # The formatted summary rounds p values; FDR requires full precision.
        test_df['p-adj'] = test_results.pvalues
        test_df['statistic'] = np.nan
    elif test_type == 'dunnett':
        control_data = df[df['group'] == order[0]]['mean_intensity'].values
        experimental_data = [df[df['group'] == group]['mean_intensity'].values for group in order[1:]]
        test_stats = dunnett(*experimental_data, control=control_data, alternative=alt)
        test_df = pd.DataFrame({
            'group1': [order[0]] * len(np.atleast_1d(test_stats.pvalue)),
            'group2': order[1:],
            'statistic': np.atleast_1d(test_stats.statistic),
            'p-adj': np.atleast_1d(test_stats.pvalue),
            'reject': np.atleast_1d(test_stats.pvalue) < 0.05,
        })
    elif test_type == 'ttest':
        test_df = perform_t_tests(df, order)

    test_df = add_group_summary_columns(test_df, df)

    p_col = 'p-value' if test_type == 'ttest' else 'p-adj'
    test_df['significance'] = test_df[p_col].apply(
        lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.'
    )

    return test_df


def apply_fdr_correction(test_df, test_type, q=0.05):
    """Correct one family containing every finite region/comparison p value."""
    if not 0 < q < 1:
        raise ValueError('q must be strictly between 0 and 1.')
    test_df = test_df.copy()
    p_col = 'p-value' if test_type == 'ttest' else 'p-adj'
    valid = np.isfinite(test_df[p_col])
    test_df['p-fdr'] = np.nan
    test_df['reject_fdr'] = False
    test_df['fdr_q'] = q
    if valid.any():
        reject, adjusted, _, _ = multipletests(
            test_df.loc[valid, p_col].to_numpy(), alpha=q, method='fdr_bh'
        )
        test_df.loc[valid, 'p-fdr'] = adjusted
        test_df.loc[valid, 'reject_fdr'] = reject
    test_df['significance_fdr'] = [
        ('****' if p < 0.0001 else '***' if p < 0.001 else
         '**' if p < 0.01 else '*') if rejected else 'n.s.'
        for p, rejected in zip(test_df['p-fdr'], test_df['reject_fdr'])
    ]
    return test_df


def plot_data(region_id, order=None, labels=None, csv_path=None, test_type='tukey', alt='two-sided', skip_plots=False, test_df=None):
    df = load_data(region_id)

    if 'group' not in df.columns:
        raise KeyError(f"    [red1]'group' column not found in the DataFrame for {region_id}. Ensure the CSV files contain the correct data.")

    region_name, region_abbr = get_region_details(region_id, csv_path)
    
    # Define a list of potential colors
    predefined_colors = [
        '#2D67C8', # blue
        '#D32525', # red
        '#27AF2E', # green
        '#FFD700', # gold
        '#FF6347', # tomato
        '#8A2BE2', # blueviolet
        # ... add more colors if needed
    ]
    
    # Check if order is provided and slice the color list accordingly
    if order:
        selected_colors = predefined_colors[:len(order)]
        group_colors = dict(zip(order, selected_colors))
    else:
        groups_in_df = df['group'].unique().tolist()
        selected_colors = predefined_colors[:len(groups_in_df)]
        group_colors = dict(zip(groups_in_df, selected_colors))

    # If group order and labels are provided, update the DataFrame
    if order and labels:
        df['group'] = df['group'].astype(pd.CategoricalDtype(categories=order, ordered=True))
        df = df.sort_values('group')
        labels_mapping = dict(zip(order, labels))
        df['group_label'] = df['group'].map(labels_mapping)
    else:
        df['group_label'] = df['group']

    if test_df is None:
        test_df = run_stats(df, order, test_type, alt)
    else:
        test_df = test_df.copy()
    test_df['region_ID'] = region_id
    test_df['region'] = region_name
    test_df['abbr'] = region_abbr

    if skip_plots:
        return test_df
    
    if 'reject_fdr' not in test_df:
        raise ValueError('Plotting requires FDR-corrected results from all regions.')

    # Bar plot
    plt.figure(figsize=(4, 4))
    ax = sns.barplot(x='group_label', y='mean_intensity', data=df, color='white', errorbar=('se'), capsize=0.1, linewidth=2, edgecolor='black')

    # Formatting
    ax.set_ylabel('Mean IF Intensity', weight='bold')
    ax.set_xticks(np.arange(len(df['group_label'].unique())))
    ax.set_xticklabels(ax.get_xticklabels(), weight='bold')
    ax.tick_params(axis='both', which='major', width=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2)
    ax.spines['left'].set_linewidth(2)

    # Swarm plot
    sns.swarmplot(x='group_label', y='mean_intensity', hue='group', data=df, palette=group_colors, size=8, linewidth=1, edgecolor='black')
    
    # Remove the legend created by hue
    if ax.legend_:
        ax.legend_.remove()

    significant_comparisons = test_df[test_df['reject_fdr'] == True]

    # Calculate y-axis limits
    y_max = df['mean_intensity'].max()
    y_min = df['mean_intensity'].min()
    height_diff = (y_max - y_min) * 0.1
    y_pos = y_max + 0.5 * height_diff

    groups = df['group'].unique()

    for _, row in significant_comparisons.iterrows():
        group1, group2 = row['group1'], row['group2']
        x1 = np.where(groups == group1)[0][0]
        x2 = np.where(groups == group2)[0][0]

        plt.plot([x1, x1, x2, x2], [y_pos, y_pos + height_diff, y_pos + height_diff, y_pos], lw=1.5, c='black')
        
        sig = row['significance_fdr']

        plt.text((x1+x2)*.5, y_pos + 0.8*height_diff, sig, horizontalalignment='center', size='xx-large', color='black', weight='bold')
        y_pos += 3 * height_diff

    # Ensure the y-axis starts from the minimum value, allowing for negative values
    plt.ylim(y_min - 2 * height_diff, y_pos + 2 * height_diff)

    ax.set_xlabel('') ### was None

    # Save the plot
    output_folder = Path('regional_mean_IF_summary')
    output_folder.mkdir(parents=True, exist_ok=True)

    title = f"{region_name} ({region_abbr})\nFDR q = {test_df['fdr_q'].iloc[0]:g}"
    wrapped_title = textwrap.fill(title, 42)  # wraps at x characters. Adjust as needed.
    plt.title(wrapped_title)
    plt.tight_layout()
    region_abbr = region_abbr.replace("/", "-") # Replace problematic characters for file paths

    is_significant = not significant_comparisons.empty
    file_prefix = '_' if is_significant else ''
    file_name = f"{file_prefix}region_{region_id}_{region_abbr}.pdf"
    plt.savefig(output_folder / file_name)
    # Remove the opposite significance prefix left by an earlier run.
    stale_name = f"{'' if is_significant else '_'}region_{region_id}_{region_abbr}.pdf"
    (output_folder / stale_name).unlink(missing_ok=True)

    plt.close()

    return test_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if (args.order and not args.labels) or (not args.order and args.labels):
        raise ValueError("Both --order and --labels must be provided together.")

    if args.order and args.labels and len(args.order) != len(args.labels):
        raise ValueError("The number of entries in --order and --labels must match.")

    if not args.order or len(args.order) < 2:
        raise ValueError("At least two groups are required for comparison.")
    
    if args.test is not None:
        test_type = args.test
    elif len(args.order) == 2:
        test_type = 'ttest'
    elif len(args.order) > 2:
        test_type = 'tukey'
    
    # Print CSVs in the working dir
    print(f'\n[bold]CSVs in the working dir to process (the first word defines the groups): \n')
    for filename in os.listdir():
        if filename.endswith('.csv'):
            print(f'    {filename}')
    print()

    # If region IDs are provided using -r, use them; otherwise, get all region IDs from the CSV
    if args.lut == "CCFv3-2020__regionID_side_IDpath_region_abbr.csv":
        lut = Path(__file__).parent.parent / 'core' / 'csvs' / args.lut
    else:
        lut = Path(args.lut)
        if not lut.exists():
            raise FileNotFoundError(f"LUT CSV '{lut}' not found. Please provide a valid path.")
    region_ids_to_process = args.region_ids if args.region_ids else get_all_region_ids(lut)

    # Filter region IDs based on max Region_Intensity in input CSVs
    max_region_id = get_max_region_id_from_csvs()
    region_ids_to_process = filter_region_ids(region_ids_to_process, max_region_id)

    # Remove regions with Mean_IF_Intensity of 0 across all input CSVs
    region_ids_to_process = remove_zero_intensity_regions(region_ids_to_process)

    test_results = []

    if not region_ids_to_process:
        raise ValueError('No nonzero regions remain to test.')

    # Collect every test before correcting or plotting.
    for region_id in region_ids_to_process:
        test_df = plot_data(region_id, args.order, args.labels, csv_path=lut, test_type=test_type, alt=args.alternate, skip_plots=True)
        test_results.append(test_df)

    test_df_all = apply_fdr_correction(
        pd.concat(test_results, ignore_index=True), test_type, q=args.q
    )
    if not args.skip_plots:
        for region_id in region_ids_to_process:
            plot_data(
                region_id, args.order, args.labels, csv_path=lut,
                test_type=test_type, alt=args.alternate,
                test_df=test_df_all[test_df_all['region_ID'] == region_id],
            )

    id_cols = ['region_ID', 'region', 'abbr']
    stats_cols = [
        'group1',
        'group2',
        # 'statistic',
        'p-value', # Used for t-tests
        'p-adj', # Used for Dunnett's and Tukey's tests
        # 'reject',
        'significance',
        'p-fdr',
        'reject_fdr',
        'significance_fdr',
        'fdr_q',
        'n_group1',
        'n_group2',
        'mean_group1',
        'mean_group2',
        'diff_group2_minus_group1',
    ]
    keep_cols = id_cols + [col for col in stats_cols if col in test_df_all.columns]
    test_df_all = test_df_all[keep_cols]

    output_folder = Path('regional_mean_IF_summary')
    output_folder.mkdir(parents=True, exist_ok=True)

    output_csv = output_folder / f'regional_mean_IF_summary_{test_type}.csv'
    test_df_all.to_csv(output_csv, index=False)

    print(f'\n{test_df_all}\n')
    print(f'Summary CSV saved to ./{output_csv}')

    verbose_end_msg()
    

if __name__ == '__main__':
    main()