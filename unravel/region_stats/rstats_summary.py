#!/usr/bin/env python3

"""
Use ``rstats_summary`` (``rss``) from UNRAVEL to plot and summarize region-wise results.

Prereqs:
    - ``rstats`` and ``agg`` to calculate regional stats and aggregate them to a single directory for analysis and plotting.

Inputs:
    - CSV files from rstats (example naming: <condition>_sample??_regional_<cell or label>_densities.csv or <condition>_sample??_regional_mean_in_seg.csv)
    - CSV files from rstats (example naming: <condition>_sample??_regional_cell_densities.csv or <condition>_sample??_regional_mean_in_seg.csv)
    - Input CSV columns: Region_ID, Side, ID_Path, Region, Abbr, <OneWordCondition>_sample??
    - The <OneWordCondition>_sample?? column has the values for each region
    - sample?? should be one word too (e.g., sample07 not sample_07)

Outputs:
    - Saved to ./<test_type>_plots_<side>
    - Plots for each region with values for each group (e.g., Saline, MDMA, Meth)
    - Summary of significant differences between groups
    - regional_values_all.csv (Columns: columns: Region_ID,Side,Name,Abbr,Saline_sample06,Saline_sample07,...,MDMA_sample01,...,Meth_sample23,...)
    - Optionally: regional_values_all_w_hemi_exclusions.csv (same as above but with hemispheres excluded based on --exclude_hemi)

Note: 
    - Example hex code list (flank arg w/ double quotes): ['#2D67C8', '#27AF2E', '#D32525', '#7F25D3']
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020_regional_summary.csv
    - It has columns: Region_ID, ID_Path, Region, Abbr, General_Region, R, G, B
    - Alternatively, use CCFv3-2017_regional_summary.csv or provide a custom CSV with the same columns.

Usage for Tukey tests:
----------------------
    rstats_summary --groups Saline MDMA Meth --side both [-i <input_pattern>] [-y cell_density | label_density | y axis name] [-div 10000] [-csv CCFv3-2020_regional_summary.csv] [-b ABA] [-s light:white] [-o tukey_plots] [-e pdf] [-eh sample07:R sample12:L] [-v]

Usage for t-tests:
------------------
    rstats_summary --groups Saline MDMA --side both -c Saline [-i <input_pattern>] [-alt two-sided] [-y cell_density | label_density | y axis name] [-div 10000] [-csv CCFv3-2020_regional_summary.csv] [-b ABA] [-s light:white] [-o t-test_plots] [-e pdf] [-eh sample07:R sample12:L] [-v]


Usage for mean intensity in segmentation mask within each region:
-----------------------------------------------------------------
    rstats_summary --groups Saline LPS --side both -i '`*`mean_in_seg.csv' -y 'Mean Iba1-IF in segmentation mask'

"""

import ast
import os
from pathlib import Path
import re
import matplotlib as mpl
mpl.use("Agg")  # Must be before importing pyplot to suppress error about session managment (not relevant here since we're saving plots, not showing them)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import textwrap
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.stats import ttest_ind, dunnett
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-g', '--groups', nargs='*', help='Group prefixes (e.g., saline meth mdma)', required=True, action=SM)
    reqs.add_argument('-s', '--side', help='Side of brain to process (r, l or both)', choices=['r', 'l', 'both'], required=True, action=SM)
    reqs.add_argument('-i', '--input', help="Glob pattern for input CSV files (e.g. '*cell_densities.csv')", required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--ctrl_group', help="Control group name for t-test or Dunnett's tests", action=SM)  # Does the control need to be specified for a t-test? First group could be the control.
    opts.add_argument('-alt', '--alternate', help="Number of tails and direction for t-tests or Dunnett's tests ('two-sided' \[default], 'less' [group1 < group2], or 'greater')", default='two-sided', action=SM)
    opts.add_argument('-y', '--ylabel', help='Y-axis label (Default: value). cell_density --> Cells*10^4/mm^3 (if -d 10000), label_density --> Label volume (percent), or use custom text', default='value', action=SM)
    opts.add_argument('-d', '--divide', type=float, help='Divide the cell densities by the specified value for plotting (default is None)', default=None, action=SM)
    opts.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020_regional_summary.csv', default='CCFv3-2020_regional_summary.csv', action=SM)
    opts.add_argument('-b', '--bar_color', help="ABA (default), #hex_code, Seaborn palette, or #hex_code list matching # of groups", default='ABA', action=SM)
    opts.add_argument('-sc', '--symbol_color', help="ABA, #hex_code, Seaborn palette (Default: light:white), or #hex_code list matching # of groups", default='light:white', action=SM)
    opts.add_argument('-o', '--output', help='Output directory for plots (Default: <t-test or tukey>_plots)', action=SM)
    opts.add_argument('-e', '--extension', help='File extension for plots. Choices: pdf (default), svg, eps, tiff, png)', default='pdf', choices=['pdf', 'svg', 'eps', 'tiff', 'png'], action=SM)
    opts.add_argument('-eh', '--exclude_hemi', help='Exclude one hemisphere for specific samples. Example: --exclude_hemi sample07:R sample12:L', nargs='*', default=[], action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Dunnett's test. LH/RH averaging via summing counts and volumes before dividing counts by volumes (rather than averaging densities directly). Set up label density quantification.
# TODO: Adapt this to work for cell counts and label densities. This could also be used for mean IF intensities.
# TODO: Need a way to handle cases when some data from some samples is from one hemisphere and some from the other. (see filter_csv.py)
# TODO: Fix plots for when there are > 3 groups (comparison lines are not positioned correctly)
# TODO: Zip the output directory to save space and make it easier to move around.

def get_region_details(region_id, df):
    # Adjust to account for the unique region IDs.
    region_row = df[(df["Region_ID"] == region_id) | (df["Region_ID"] == region_id + 20000)].iloc[0]
    return region_row["Region"], region_row["Abbr"]

def parse_color_argument(color_arg, num_groups, region_id, csv_path):
    if isinstance(color_arg, str):
        if color_arg.startswith('[') and color_arg.endswith(']'):
            # It's a string representation of a list, so evaluate it safely
            color_list = ast.literal_eval(color_arg)    
            if len(color_list) != num_groups:
                raise ValueError(f"The number of colors provided ({len(color_list)}) does not match the number of groups ({num_groups}).")
            return color_list
        elif color_arg.startswith('#'):
            # It's a single hex color, use it for all groups
            return [color_arg] * num_groups
        elif color_arg == 'ABA':
            # Determine the RGB color for bars based on the region_id
            combined_region_id = region_id if region_id < 20000 else region_id - 20000
            if csv_path == 'CCFv3-2017_regional_summary.csv' or csv_path == 'CCFv3-2020_regional_summary.csv': 
                results_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
            else:
                results_df = pd.read_csv(csv_path)
            region_rgb = results_df[results_df['Region_ID'] == combined_region_id][['R', 'G', 'B']]
            rgb = tuple(region_rgb.iloc[0].values)
            rgb_normalized = tuple([x / 255.0 for x in rgb])
            ABA_color = sns.color_palette([rgb_normalized] * num_groups)
            return ABA_color
        else:
            # It's a named seaborn palette
            return sns.color_palette(color_arg, num_groups)
    else:
        # It's already a list (this would be the case for default values or if the input method changes)
        return color_arg    

def _sample_from_col(col: str) -> str | None:
    """Extract the sample name (e.g., "sample07") from a column name like "Saline_sample07".
    
    Args:
        - col (str): the column name from which to extract the sample name

    Returns:
        - str or None: the extracted sample name in lowercase (e.g., "sample07") or None if no sample name is found
    """
    m = col.split('_')[-1] if '_' in col else None
    return m.lower() if m else None

def parse_exclude_hemi(exclude_args: list[str]) -> dict[str, str]:
    """Parse the --exclude_hemi arguments to determine which hemisphere to exclude for specific samples.

    Args:
        - exclude_args (list of str): List of strings in the format "sampleNN:R" or "sampleNN:L" indicating which hemisphere to exclude for each sample.

    Returns: 
        - dict mapping sample names (e.g., "sample07") to the hemisphere to exclude ("R" or "L"). For example, {"sample07": "R", "sample12": "L"}.
    """
    exclude_hemi_dict: dict[str, str] = {}
    for item in exclude_args or []:
        if ':' not in item:
            raise ValueError(f"--exclude_hemi must be like sampleNN:R (got {item})")
        samp, side = item.split(':', 1)
        samp = samp.strip().lower()
        side = side.strip().upper()
        if side not in {"L", "R"}:
            raise ValueError(f"Invalid side in --exclude_hemi '{item}'. Use L or R.")
        exclude_hemi_dict[samp] = side
    return exclude_hemi_dict

def mask_excluded_side(side_df: pd.DataFrame, side_letter: str, exclude_map: dict[str, str]) -> pd.DataFrame:
    """Mask the data for the specified side if it is marked for exclusion in the exclude_map.
    Args:
        - side_df (DataFrame): the DataFrame containing the data for the current side (columns: Region_ID, Side, ID_Path, Region, Abbr, <group_sample??>, ...)
        - side_letter (str): the letter representing the current side ("L" or "R")
        - exclude_map (dict): a dictionary mapping sample names to the hemisphere to exclude (e.g., {"sample07": "R", "sample12": "L"})
    Returns:
        - DataFrame: the modified DataFrame with the specified side masked (set to NaN) for the samples that are marked for exclusion in the exclude_map
    """
    if not exclude_map:
        return side_df
    side_df = side_df.copy()
    for col in side_df.columns[5:]: # Only check columns with sample data, not the first 5 metadata columns
        samp = _sample_from_col(col)
        if samp and exclude_map.get(samp) == side_letter:
            side_df[col] = np.nan
    return side_df

def summarize_significance(test_df, id):
    """Summarize the results of the statistical tests.
    
    Args:
        - test_df (DataFrame): the DataFrame containing the test results (w/ columns: group1, group2, p-value, meandiff)
        - id (int): the region or cluster ID

    Returns:
        - summary_df (DataFrame): the DataFrame containing the summarized results
    """
    summary_rows = []
    for _, row in test_df.iterrows():
        group1, group2 = row['group1'], row['group2']
        # Determine significance level
        sig = ''
        if row['p-value'] < 0.0001:
            sig = '****'
        elif row['p-value'] < 0.001:
            sig = '***'
        elif row['p-value'] < 0.01:
            sig = '**'
        elif row['p-value'] < 0.05:
            sig = '*'
        # Determine which group has a higher mean
        meandiff = row['meandiff']
        higher_group = group2 if meandiff > 0 else group1
        summary_rows.append({
            'Region_ID': id,
            'Comparison': f'{group1} vs {group2}',
            'p-value': row['p-value'],
            'Higher_Mean_Group': higher_group,
            'Significance': sig
        })
    return pd.DataFrame(summary_rows)

def process_and_plot_data(df, region_id, region_name, region_abbr, side, out_dir, group_columns, test_type, args):
    """Process the data for a specific region and create a bar plot with statistical comparisons."""

    # Reshaping the data for plotting
    reshaped_data = []
    for prefix in args.groups:
        for value in df[group_columns[prefix]].values.ravel():
            reshaped_data.append({'group': prefix, 'value': value})
    reshaped_df = pd.DataFrame(reshaped_data)

    # Plotting
    mpl.rcParams['font.family'] = 'Arial'
    plt.figure(figsize=(4, 4))

    groups = reshaped_df['group'].unique()
    num_groups = len(groups)

    # Parse the color arguments
    bar_color = parse_color_argument(args.bar_color, num_groups, region_id, args.csv_path)
    symbol_color = parse_color_argument(args.symbol_color, num_groups, region_id, args.csv_path)

    # Coloring the bars and symbols
    # ax = sns.barplot(x='group', y='value', data=reshaped_df, errorbar=('se'), capsize=0.1, palette=bar_color, linewidth=2, edgecolor='black')
    ax = sns.barplot(x='group', y='value', hue='group', data=reshaped_df, errorbar=('se'), capsize=0.1, palette=bar_color, linewidth=2, edgecolor='black', legend=False)
    sns.stripplot(x='group', y='value', hue='group', data=reshaped_df, palette=symbol_color, alpha=0.5, size=8, linewidth=0.75, edgecolor='black')

    # Calculate y_max and y_min based on the actual plot
    y_max = ax.get_ylim()[1]
    y_min = ax.get_ylim()[0]
    height_diff = (y_max - y_min) * 0.05  # Adjust the height difference as needed
    y_pos = y_max * 1.05  # Start just above the highest bar

    # Check which test to perform
    if test_type == 't-test':
        # Perform t-test for each group against the control group
        control_data = pd.to_numeric(df[group_columns[args.ctrl_group]].values.ravel(), errors="coerce") # Convert to numeric and coerce errors to NaN (in case there are any non-numeric values)
        control_data = control_data[~np.isnan(control_data)] # Remove NaN values that may have been introduced by hemisphere exclusions

        test_results = []
        for prefix in args.groups:
            if prefix != args.ctrl_group:
                # other_group_data = df[group_columns[prefix]].values.ravel()
                other_group_data = pd.to_numeric(df[group_columns[prefix]].values.ravel(), errors="coerce")
                other_group_data = other_group_data[~np.isnan(other_group_data)]

                t_stat, p_value = ttest_ind(other_group_data, control_data, equal_var=True, alternative=args.alternate) # Switched to equal_var=True and alternative=args.alternate
                meandiff = np.mean(other_group_data) - np.mean(control_data)
                # if args.alternate == 'less' and meandiff < 0:
                #     p_value /= 2  # For one-tailed test, halve the p-value if the alternative is 'less'
                #     t_stat = -t_stat  # Flip the sign for 'less'
                # elif args.alternate == 'greater' and meandiff > 0:
                #     p_value /= 2  # For one-tailed test, halve the p-value if the alternative is 'greater'
                # elif args.alternate == 'two-sided':
                #     pass # No change in p value needed for two-sided test
                # else: # Effect direction not consistent with hypothesis 
                #     p_value = 1
                test_results.append({
                    'group1': args.ctrl_group,
                    'group2': prefix,
                    't-stat': t_stat,
                    'p-value': p_value,
                    'meandiff': np.mean(other_group_data) - np.mean(control_data)
                })

        test_results_df = pd.DataFrame(test_results)
        significant_comparisons = test_results_df[test_results_df['p-value'] < 0.05]

    elif test_type == 'dunnett':

        # Extract the data for the control group and the other groups
        data = [df[group_columns[prefix]].values.ravel() for prefix in args.groups if prefix != args.ctrl_group]
        control_data = df[group_columns[args.ctrl_group]].values.ravel()

        # The * operator unpacks the list so that each array is a separate argument, as required by dunnett
        dunnett_results = dunnett(*data, control=control_data, alternative=args.alternate)

        group2_data = [df[group_columns[prefix]].values.ravel() for prefix in args.groups if prefix != args.ctrl_group]

        # Convert the result to a DataFrame
        test_results_df = pd.DataFrame({
            'group1': [args.ctrl_group] * len(dunnett_results.pvalue),
            'group2': [prefix for prefix in args.groups if prefix != args.ctrl_group],
            'p-value': dunnett_results.pvalue,
            'meandiff': np.mean(group2_data, axis=1) - np.mean(control_data) # Calculate the mean difference between each group and the control group
        })
        significant_comparisons = test_results_df[test_results_df['p-value'] < 0.05]

    elif test_type == 'tukey':

        # Conduct Tukey's HSD test
        values_list = []
        groups_list = []
        for prefix in args.groups:
            vals = pd.to_numeric(df[group_columns[prefix]].values.ravel(), errors="coerce")
            vals = vals[~np.isnan(vals)]
            values_list.extend(vals.tolist())
            groups_list.extend([prefix] * len(vals))

        values = np.array(values_list, dtype=float)
        groups = np.array(groups_list, dtype=object)

        tukey_results = pairwise_tukeyhsd(values, groups, alpha=0.05)

        # Extract significant comparisons from Tukey's results
        test_results_df = pd.DataFrame(data=tukey_results.summary().data[1:], columns=tukey_results.summary().data[0])
        test_results_df.rename(columns={'p-adj': 'p-value'}, inplace=True)
        significant_comparisons = test_results_df[test_results_df['p-value'] < 0.05]

    # Loop for plotting comparison bars and asterisks
    for _, row in significant_comparisons.iterrows():
        group1, group2 = row['group1'], row['group2']
        x1 = np.where(groups == group1)[0][0]
        x2 = np.where(groups == group2)[0][0]

        # Plotting comparison lines
        plt.plot([x1, x1, x2, x2], [y_pos, y_pos + height_diff, y_pos + height_diff, y_pos], lw=1.5, c='black')
        
        # Plotting asterisks based on p-value
        if row['p-value'] < 0.0001:
            sig = '****'
        elif row['p-value'] < 0.001:
            sig = '***'
        elif row['p-value'] < 0.01:
            sig = '**'
        else:
            sig = '*'
        plt.text((x1 + x2) * .5, y_pos + 1 * height_diff, sig, horizontalalignment='center', size='xx-large', color='black', weight='bold')

        y_pos += 3 * height_diff  # Increment y_pos for the next comparison bar

    # Remove the legend only if it exists
    if ax.get_legend():
        ax.get_legend().remove()

    # Format the plot
    if args.ylabel == 'cell_density' and args.divide == 10000:
        ax.set_ylabel(r'Cells*10$^{4} $/mm$^{3}$', weight='bold')
    elif args.ylabel == 'label_density':
        ax.set_ylabel(r'Label volume (%)', weight='bold')
    else:
        ax.set_ylabel(args.ylabel, weight='bold')

    ax.set_xticks(range(len(ax.get_xticklabels())))  # Set ticks based on current tick labels
    ax.set_xticklabels(ax.get_xticklabels(), weight='bold')
    ax.tick_params(axis='both', which='major', width=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2)
    ax.spines['left'].set_linewidth(2)
    plt.ylim(0, y_pos) # Adjust y-axis limit to accommodate comparison bars
    ax.set_xlabel('') ### was None

    # Check if there are any significant comparisons (for prepending '_sig__' to the filename)
    has_significant_results = True if significant_comparisons.shape[0] > 0 else False

    # Extract the general region for the filename (output file name prefix for sorting by region)
    if args.csv_path == 'CCFv3-2017_regional_summary.csv' or args.csv_path == 'CCFv3-2020_regional_summary.csv': 
        regional_summary = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
    else:
        regional_summary = pd.read_csv(args.csv_path)
    region_id = region_id if region_id < 20000 else region_id - 20000 # Adjust if left hemi
    general_region = regional_summary.loc[regional_summary['Region_ID'] == region_id, 'General_Region'].values[0]

    # Format the filename with '_sig__' prefix if there are significant results
    prefix = '_sig__' if has_significant_results else ''
    filename = f"{prefix}{general_region}__{region_id}_{region_abbr}_{side}".replace("/", "-") # Replace problematic characters

    # Save the plot for each side or pooled data
    title = f"{region_name} ({region_abbr}, {side})"
    wrapped_title = textwrap.fill(title, 42)
    plt.title(wrapped_title, pad = 20).set_position([.5, 1.05])
    plt.tight_layout()
    plt.savefig(f"{out_dir}/{filename}.{args.extension}")
    plt.close()

    return test_results_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    if args.exclude_hemi:
        exclude_map = parse_exclude_hemi(args.exclude_hemi)
    else:
        exclude_map = {}

    if exclude_map and args.verbose:
        print("\nHemisphere exclusions:")
        for samp, side in sorted(exclude_map.items()):
            print(f"  {samp}: {side}")
        print()

    if len(args.groups) == 2:
        test_type = 't-test'
    elif len(args.groups) > 2:
        test_type = 'tukey'

    file_list = match_files(args.input)

    if not file_list:
        print(f"\n[red1]No files found matching the pattern '{args.input}'.\n")
        return
    is_label_density_input = any('label_densities' in str(f) for f in file_list)

    # Aggregate the data for each sample into a single DataFrame. Start with the first file to get the metadata columns, then add the sample columns from each subsequent file.
    aggregated_df = pd.read_csv(file_list[0]).iloc[:, 0:5].copy()

    for file_name in file_list:
        file_df = pd.read_csv(file_name)

        data_cols = [c for c in file_df.columns[5:]]

        rename_map = {}
        for col in data_cols:
            for prefix in args.groups:
                if prefix.lower() in col.lower():
                    old_prefix = col.split("_")[0]
                    rename_map[col] = col.replace(old_prefix, prefix)
                    break

        file_df = file_df.rename(columns=rename_map)

        cols_to_add = [c for c in file_df.columns if c not in aggregated_df.columns[:5]]
        aggregated_df = pd.concat([aggregated_df, file_df[cols_to_add]], axis=1)


    # Sort all columns that are not part of the first five by group prefix
    all_data_columns = aggregated_df.columns[5:].tolist()
    support_columns = [c for c in all_data_columns if c.endswith('_support')]
    numerator_columns = [c for c in all_data_columns if c.endswith('_numerator')]
    denominator_columns = [c for c in all_data_columns if c.endswith('_denominator')]
    value_columns = [
        c for c in all_data_columns
        if not c.endswith('_support')
        and not c.endswith('_numerator')
        and not c.endswith('_denominator')
    ]

    sorted_value_columns = []
    sorted_support_columns = []
    sorted_numerator_columns = []
    sorted_denominator_columns = []

    for prefix in args.groups:
        prefixed_value_cols = [col for col in value_columns if col.startswith(f"{prefix}_")]
        prefixed_support_cols = [col for col in support_columns if col.startswith(f"{prefix}_")]
        prefixed_numerator_cols = [col for col in numerator_columns if col.startswith(f"{prefix}_")]
        prefixed_denominator_cols = [col for col in denominator_columns if col.startswith(f"{prefix}_")]

        sorted_value_columns += sorted(prefixed_value_cols, key=lambda x: int(re.search(r'\d+', x).group()))
        sorted_support_columns += sorted(prefixed_support_cols, key=lambda x: int(re.search(r'\d+', x).group()))
        sorted_numerator_columns += sorted(prefixed_numerator_cols, key=lambda x: int(re.search(r'\d+', x).group()))
        sorted_denominator_columns += sorted(prefixed_denominator_cols, key=lambda x: int(re.search(r'\d+', x).group()))

    sorted_columns = (
        aggregated_df.columns[:5].tolist()
        + sorted_support_columns
        + sorted_numerator_columns
        + sorted_denominator_columns
        + sorted_value_columns
    )

    df = aggregated_df[sorted_columns]

    # Save the aggregated data as a CSV
    df.to_csv('regional_values_all.csv', index=False)


    if args.exclude_hemi:
        # Also save a masked version with hemisphere exclusions applied (analysis-ready)
        df_masked = df.copy()
        if exclude_map:
            # Mask RH rows
            rh_rows = df_masked["Side"].astype(str).str.upper().eq("R")
            df_masked.loc[rh_rows] = mask_excluded_side(df_masked.loc[rh_rows], "R", exclude_map)

            # Mask LH rows
            lh_rows = df_masked["Side"].astype(str).str.upper().eq("L")
            df_masked.loc[lh_rows] = mask_excluded_side(df_masked.loc[lh_rows], "L", exclude_map)

        df_masked.to_csv("regional_values_all_w_hemi_exclusions.csv", index=False)


    # Prepare output directories
    if args.alternate == 'two-sided':
        suffix = ''
    else:
        suffix = f"_{args.alternate}" # Add suffix to indicate the alternative hypothesis

    # Make output directories
    if args.output:
        if args.side == 'both': 
            out_dirs = {side: f"{args.output}_{side}{suffix}" for side in ["L", "R", "pooled"]}
        elif args.side == 'r': 
            out_dirs = {side: f"{args.output}_{side}{suffix}" for side in ["R"]}
        elif args.side == 'l': 
            out_dirs = {side: f"{args.output}_{side}{suffix}" for side in ["L"]}
        else: 
            print("--side should be l, r, or both")
            import sys ; sys.exit()
    else:
        if args.side == 'both': 
            out_dirs = {side: f"{test_type}_plots_{side}{suffix}" for side in ["L", "R", "pooled"]}
        elif args.side == 'r': 
            out_dirs = {side: f"{test_type}_plots_{side}{suffix}" for side in ["R"]}
        elif args.side == 'l': 
            out_dirs = {side: f"{test_type}_plots_{side}{suffix}" for side in ["L"]}
        else: 
            print("--side should be l, r, or both")
            import sys ; sys.exit()

    for out_dir in out_dirs.values():
        os.makedirs(out_dir, exist_ok=True)
    
    group_columns = {}
    support_group_columns = {}
    numerator_group_columns = {}
    denominator_group_columns = {}

    for prefix in args.groups:
        group_columns[prefix] = [col for col in df.columns if col.startswith(f"{prefix}_") and not col.endswith('_support') and not col.endswith('_numerator') and not col.endswith('_denominator')]
        support_group_columns[prefix] = [col for col in df.columns if col.startswith(f"{prefix}_") and col.endswith('_support')]
        numerator_group_columns[prefix] = [col for col in df.columns if col.startswith(f"{prefix}_") and col.endswith('_numerator')]
        denominator_group_columns[prefix] = [col for col in df.columns if col.startswith(f"{prefix}_") and col.endswith('_denominator')]

    missing_groups = [g for g, cols in group_columns.items() if len(cols) == 0]

    if missing_groups:
        available = [c for c in df.columns[5:]]

        raise ValueError(
            "\nNo data columns were found for the following groups:\n"
            f"  {', '.join(missing_groups)}\n\n"
            "rstats_summary expects data columns to begin with the group name (one word before the first underscore; "
            "e.g. 'saline_sample01', 'drug_sample02').\n\n"
            "Available columns include:\n"
            f"  {available[:10]}"
        )

    # Normalization if needed
    if args.divide:
        value_cols_only = [col for cols in group_columns.values() for col in cols]
        df[value_cols_only] = df[value_cols_only].div(args.divide)

    if args.side == 'both': 
        # Averaging data across hemispheres and plotting pooled data (DR)
        print(f"\nPlotting and summarizing pooled data for each region...\n")
        rh_df = df[df['Region_ID'] < 20000]
        lh_df = df[df['Region_ID'] > 20000]

        # Initialize an empty dataframe to store all summaries
        all_summaries_pooled = pd.DataFrame() 

        rh_df = rh_df.reset_index(drop=True)
        lh_df = lh_df.reset_index(drop=True)

        pooled_df = df[['Region_ID', 'Side', 'ID_Path', 'Region', 'Abbr']][df['Region_ID'] < 20000].reset_index(drop=True)
        pooled_df['Side'] = 'Pooled'

        for prefix in args.groups:
            for value_col in group_columns[prefix]:
                samp = _sample_from_col(value_col)
                ex = exclude_map.get(samp) if samp else None

                lh_value = lh_df[value_col].reset_index(drop=True)
                rh_value = rh_df[value_col].reset_index(drop=True)

                support_col = f"{value_col}_support"
                numerator_col = f"{value_col}_numerator"
                denominator_col = f"{value_col}_denominator"

                # Case 1: mean metrics -> weighted mean by support
                if support_col in lh_df.columns and support_col in rh_df.columns:
                    lh_support = lh_df[support_col].reset_index(drop=True)
                    rh_support = rh_df[support_col].reset_index(drop=True)

                    if ex == "R":
                        pooled_df[support_col] = lh_support
                        pooled_df[value_col] = lh_value
                    elif ex == "L":
                        pooled_df[support_col] = rh_support
                        pooled_df[value_col] = rh_value
                    else:
                        total_support = lh_support + rh_support
                        pooled_df[support_col] = total_support
                        pooled_df[value_col] = np.where(
                            total_support > 0,
                            (lh_value * lh_support + rh_value * rh_support) / total_support,
                            np.nan
                        )

                # Case 2: density metrics -> recompute from summed numerator and denominator
                elif numerator_col in lh_df.columns and numerator_col in rh_df.columns and denominator_col in lh_df.columns and denominator_col in rh_df.columns:
                    lh_num = lh_df[numerator_col].reset_index(drop=True)
                    rh_num = rh_df[numerator_col].reset_index(drop=True)
                    lh_den = lh_df[denominator_col].reset_index(drop=True)
                    rh_den = rh_df[denominator_col].reset_index(drop=True)

                    if ex == "R":
                        pooled_df[numerator_col] = lh_num
                        pooled_df[denominator_col] = lh_den
                    elif ex == "L":
                        pooled_df[numerator_col] = rh_num
                        pooled_df[denominator_col] = rh_den
                    else:
                        pooled_df[numerator_col] = lh_num + rh_num
                        pooled_df[denominator_col] = lh_den + rh_den

                    if is_label_density_input:
                        pooled_df[value_col] = np.where(
                            pooled_df[denominator_col] > 0,
                            pooled_df[numerator_col] / pooled_df[denominator_col] * 100,
                            np.nan
                        )
                    else:
                        pooled_df[value_col] = np.where(
                            pooled_df[denominator_col] > 0,
                            pooled_df[numerator_col] / pooled_df[denominator_col],
                            np.nan
                        )

                # Fallback
                else:
                    if ex == "R":
                        pooled_df[value_col] = lh_value
                    elif ex == "L":
                        pooled_df[value_col] = rh_value
                    else:
                        pooled_df[value_col] = (lh_value + rh_value) / 2
        
        # Save the pooled data to a CSV for reference
        if args.divide:
            pooled_df.to_csv(f'regional_values_pooled_div{str(int(args.divide))}.csv', index=False)
        else:
            pooled_df.to_csv('regional_values_pooled.csv', index=False)

        # Averaging data across hemispheres and plotting pooled data
        unique_region_ids = df[df["Side"] == "R"]["Region_ID"].unique()
        progress, task_id = initialize_progress_bar(len(unique_region_ids), "[red]Processing regions (pooled)...")
        with Live(progress):
            for region_id in unique_region_ids:
                region_name, region_abbr = get_region_details(region_id, df)
                out_dir = out_dirs["pooled"]
                comparisons_summary = process_and_plot_data(pooled_df[pooled_df["Region_ID"] == region_id], region_id, region_name, region_abbr, "Pooled", out_dir, group_columns, test_type, args)
                summary_df = summarize_significance(comparisons_summary, region_id)
                all_summaries_pooled = pd.concat([all_summaries_pooled, summary_df], ignore_index=True)
                progress.update(task_id, advance=1)

        # Merge with the original CCFv3-2020_regional_summary.csv and write to a new CSV
        if args.csv_path == 'CCFv3-2017_regional_summary.csv' or args.csv_path == 'CCFv3-2020_regional_summary.csv': 
            regional_summary = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
        else:
            regional_summary = pd.read_csv(args.csv_path)
        final_summary_pooled = pd.merge(regional_summary, all_summaries_pooled, on='Region_ID', how='left') 
        final_summary_pooled.to_csv(Path(out_dir) / '__significance_summary_pooled.csv', index=False)

    # Perform analysis and plotting for each hemisphere
    if args.side == 'r':
        sides_to_process = ["R"]
    elif args.side == 'l': 
        sides_to_process = ["L"]
    else:
        sides_to_process = ["L", "R"]

    for side in sides_to_process:
        print(f"\nPlotting and summarizing data for {side} hemisphere...\n")

        # Initialize an empty dataframe to store all summaries
        all_summaries = pd.DataFrame()
        side_df = df[df['Side'] == side]
        side_df = mask_excluded_side(side_df, side, exclude_map)
        unique_region_ids = side_df["Region_ID"].unique() # Get unique region IDs for the current side
        progress, task_id = initialize_progress_bar(len(unique_region_ids), f"[red]Processing regions ({side})...")
        with Live(progress):
            for region_id in unique_region_ids:
                region_name, region_abbr = get_region_details(region_id, side_df)
                out_dir = out_dirs[side]
                comparisons_summary = process_and_plot_data(side_df[side_df["Region_ID"] == region_id], region_id, region_name, region_abbr, side, out_dir, group_columns, test_type, args)
                summary_df = summarize_significance(comparisons_summary, region_id)
                all_summaries = pd.concat([all_summaries, summary_df], ignore_index=True)
                progress.update(task_id, advance=1)

        # Merge with the original CCFv3-2020_regional_summary.csv and write to a new CSV
        if args.csv_path == 'CCFv3-2017_regional_summary.csv' or args.csv_path == 'CCFv3-2020_regional_summary.csv': 
            regional_summary = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
        else:
            regional_summary = pd.read_csv(args.csv_path)

        # Adjust Region_ID for left hemisphere
        if side == "L":
            all_summaries["Region_ID"] = all_summaries["Region_ID"] - 20000

        final_summary = pd.merge(regional_summary, all_summaries, on='Region_ID', how='left') 
        final_summary.to_csv(Path(out_dir) / f'__significance_summary_{side}.csv', index=False)

    verbose_end_msg()


if __name__ == '__main__':
    main()
