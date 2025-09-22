#!/usr/bin/env python3

"""
Use ``cstats`` (``cs``) from UNRAVEL to validate clusters based on statistical comparisons.

Supports:
    - Pairwise comparisons (t-test, directional or two-sided)
    - Dunnett's test (one control vs multiple groups; control must appear only as the first group)
    - Holm-Šidák correction (for arbitrary pairwise tests)
    - Main-effect or interaction ANOVA (1-way or 2-way) with an external condition-to-factor map
    - Tukey's HSD (if ``--comparisons all``)

Input files:
    - `*_density_data.csv` from ``cstats_validation`` (in each subdir named after the cluster mask)

Outputs:
    - ./_valid_clusters_stats/ with raw data, stats results, and summary info

Note: 
    - This script will loop through all directories in the current working dir and process the data in each subdir.
    - Each subdir should contain .csv files with the density data for each cluster.
    - Clusters are considered valid if the number of significant comparisons meets the validation criteria.

Input CSV naming conventions (sides pooled if both LH and RH files exist):
    - Condition: first word before '_' in the file name
    - Side: last word before .csv (LH or RH)

Example unilateral inputs in the subdirs:
    - condition1_sample01_<cell|label>_density_data.csv 
    - condition1_sample02_<cell|label>_density_data.csv
    - condition2_sample03_<cell|label>_density_data.csv
    - condition2_sample04_<cell|label>_density_data.csv

Example bilateral inputs (if any file has _LH.csv or _RH.csv, the command will attempt to pool data):
    - condition1_sample01_<cell|label>_density_data_LH.csv
    - condition1_sample01_<cell|label>_density_data_RH.csv

Columns in the input .csv files:
    sample, cluster_ID, <cell_count|label_volume>, cluster_volume, <cell_density|label_density>, ...

Example content of a group_map CSV:
-----------------------------------
condition,Psilocybin,Housing
SalineHC,Saline,HC
SalineEE,Saline,EE
PsilocybinHC,Psilocybin,HC
PsilocybinEE,Psilocybin,EE

Usage for a one-tailed t-test
-----------------------------
    cs -c saline<MDMA

Usage for non-directional t-tests with Holm-Sidak correction:
-------------------------------------------------------------
    cs -c saline,MDMA MDMA,R-MDMA saline,R-MDMA

Usage for Tukey's test (all pairwise comparisons):
--------------------------------------------------
    cs -c all

Usage for 1-way ANOVA main effect:
----------------------------------
    cs --group_map entactogen_map.csv --formula Entactogen --effect Entactogen

Usage for 2-way ANOVA main effect:
----------------------------------
    cs --group_map psilo_housing_map.csv --formula Psilocybin+Housing --effect Psilocybin

Usage for 2-way ANOVA interaction:
----------------------------------
    cs --group_map psilo_housing_map.csv --formula Psilocybin*Housing --effect Psilocybin:Housing

Usage for testing all ANOVA terms:
----------------------------------
    cs --group_map psilo_housing_map.csv --formula Psilocybin*Housing
"""

import re
import numpy as np
import pandas as pd
from itertools import combinations
from pathlib import Path
from rich import print
from rich.traceback import install
from rich.live import Live
from scipy.stats import ttest_ind, dunnett
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.multitest import multipletests

from unravel.cluster_stats.stats_table import cluster_summary
from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, initialize_progress_bar


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts_comparisons = parser.add_argument_group('Optional args for comparisons')
    opts_comparisons.add_argument('-c', '--comparisons', help=("List of pairwise comparisons (e.g. saline<MDMA saline,R-MDMA), with the control group first. Use '<' or '>' for directional tests, or ',' for two-sided. Use 'all' for Tukey tests. "), nargs='*', default=['all'], action=SM)

    opts_anova = parser.add_argument_group('Optional args for ANOVA')
    opts_anova.add_argument('-gm', '--group_map', help='CSV file mapping condition names to factor levels (required for ANOVA).', action=SM)
    opts_anova.add_argument('-e', '--effect', help='Specific effect or interaction to validate from ANOVA (e.g., Psilocybin or Psilocybin:Housing)', default=None, action=SM)
    opts_anova.add_argument('-f', '--formula', help='ANOVA model formula (e.g., Psilocybin+Housing or Psilocybin*Housing). Required if using group_map', required=False, action=SM)

    opts_validation = parser.add_argument_group('Optional args for validation criteria and output')
    opts_validation.add_argument('-vc', '--val_crit', help="Validation criteria: 'all' (default), 'any', or a number of comparisons that must be significant for a cluster to be valid.", default='all', action=SM)
    opts_validation.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from cstats_fdr). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)
    opts_validation.add_argument('-ov', '--overwrite', help='Force re-processing even if outputs exist. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def parse_comparisons(comp_list, all_conditions):
    """
    Parse comparison strings into tuples.

    Parameters
    ----------
    comp_list : list of str
        List of comparison strings (e.g., ['saline<MDMA', 'saline,R-MDMA']).
    all_conditions : list of str
        List of all conditions present in the dataset (e.g., ['saline', 'MDMA', 'R-MDMA']).

    
    Returns
    -------
    list of tuples
        List of tuples in the format (group1, group2, direction), where direction is 'less', 'greater', or 'two-sided'.
        - group1: str, name of the first group
        - group2: str, name of the second group
        - direction: str, 'less', 'greater', or 'two-sided'
    """
    if len(comp_list) == 1 and comp_list[0].lower() == 'all':
        return [(g1, g2, 'two-sided') for g1, g2 in combinations(sorted(all_conditions), 2)]

    parsed = []
    for comp in comp_list:
        if '<' in comp:
            g1, g2 = comp.split('<')
            direction = 'less'
        elif '>' in comp:
            g1, g2 = comp.split('>')
            direction = 'greater'
        elif ',' in comp:
            g1, g2 = comp.split(',')
            direction = 'two-sided'
        else:
            raise ValueError(f"Invalid comparison format: {comp}")
        parsed.append((g1.strip(), g2.strip(), direction))
    return parsed

def valid_clusters_t_test(df, group1, group2, density_col, alternative='two-sided'):
    """Perform unpaired t-tests for each cluster in the DataFrame and return the results as a DataFrame.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the cluster data with columns 'cluster_ID', 'condition', and the density column.
    group1 : str
        Name of the first group (e.g., 'saline').
    group2 : str
        Name of the second group (e.g., 'MDMA').
    density_col : str
        Name of the column containing the density values (e.g., 'cell_density' or 'label_density').
    alternative : str, optional
        Specifies the alternative hypothesis for the t-test. Options are 'two-sided', 'less', or 'greater'.
        Default is 'two-sided'. 
    
    Returns
    -------
    pd.DataFrame
        DataFrame containing the t-test results for each cluster.
        Columns include 'cluster_ID', 'comparison', 'higher_mean_group', 'p-value', and 'significance'.
    """

    stats_df = pd.DataFrame()
    for cluster_id in df['cluster_ID'].unique():
        cluster_data = df[df['cluster_ID'] == cluster_id]
        group1_data = np.array([value for value in cluster_data[cluster_data['condition'] == group1][density_col].values.ravel()])
        group2_data = np.array([value for value in cluster_data[cluster_data['condition'] == group2][density_col].values.ravel()])
        
        # Perform unpaired two-tailed t-test
        t_stat, p_value = ttest_ind(group1_data, group2_data, equal_var=True, alternative=alternative)
        p_value = float(f"{p_value:.6f}")

        # Create a temporary DataFrame for the current t-test result
        temp_df = pd.DataFrame({'cluster_ID': [cluster_id], 'p-value': [p_value]})

        # Use pd.concat to append the temporary DataFrame
        stats_df = pd.concat([stats_df, temp_df], ignore_index=True)

    # Add a column the higher mean group
    stats_df['group1'] = group1  # Add columns for the group names
    stats_df['group2'] = group2
    stats_df['comparison'] = stats_df['group1'] + ' vs ' + stats_df['group2']
    stats_df['group1_mean'] = stats_df['cluster_ID'].apply(lambda cluster_id: df[(df['cluster_ID'] == cluster_id) & (df['condition'] == group1)][density_col].mean())
    stats_df['group2_mean'] = stats_df['cluster_ID'].apply(lambda cluster_id: df[(df['cluster_ID'] == cluster_id) & (df['condition'] == group2)][density_col].mean())
    stats_df['meandiff'] = stats_df['group1_mean'] - stats_df['group2_mean']
    stats_df['higher_mean_group'] = stats_df['meandiff'].apply(lambda diff: group1 if diff > 0 else group2)
    stats_df['significance'] = stats_df['p-value'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')

    # Update columns
    stats_df.drop(columns=['group1_mean', 'group2_mean', 'meandiff', 'group1', 'group2'], inplace=True)
    stats_df = stats_df[['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']]

    return stats_df

def match_effect(aov_term, effect_of_interest):
    """Match effect name ignoring C() wrapper and case sensitivity."""
    # Remove 'C(...)' if present from patsy formula terms
    def clean(term):
        return re.sub(r'^C\((.+)\)$', r'\1', term.strip(), flags=re.IGNORECASE).lower()
    return clean(aov_term) == clean(effect_of_interest)

def valid_clusters_anova(df, density_col, formula, effect_of_interest=None):
    """
    Run per-cluster ANOVA with a user-defined model formula.

    For each cluster, fits an ANOVA model using the specified formula and reports
    the p-value(s) for the specified effect(s).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing cluster-level data. Must include 'cluster_ID',
        a condition/factor column (e.g., 'condition'), and the specified density column.
    density_col : str
        Name of the column containing the dependent variable (e.g., 'cell_density', 'label_density').
    formula : str
        Statsmodels formula specifying the model, such as:
            - 'condition1'
            - 'condition1 + condition2'
            - 'condition1 * condition2'
    effect_of_interest : str, optional
        If specified, only this effect (main effect or interaction) will be included in the output.
        Example values: 'condition1', 'condition2', 'condition1:condition2'.
        If None (default), all effects in the model will be reported.

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per cluster per reported effect.
        Columns: ['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']

    Notes
    -----
    - The formula must use valid statsmodels syntax. For example:
        * 'A + B' includes main effects of A and B
        * 'A * B' includes main effects of A and B and their interaction A:B
    - Skips clusters that fail model fitting or do not have enough variation in the dependent variable.
    - The 'higher_mean_group' field is left blank for ANOVA results, since it's not defined in multi-group tests.
    - P-values are annotated with significance levels:
        * '****' if p < 0.0001
        * '***'  if p < 0.001
        * '**'   if p < 0.01
        * '*'    if p < 0.05
        * 'n.s.' otherwise
    """
    from patsy import dmatrices, PatsyError

    rows = []
    for cluster_id in df['cluster_ID'].unique():
        sub = df[df['cluster_ID'] == cluster_id]

        # Skip if fewer than 2 unique values in the dependent variable
        if sub[density_col].nunique() < 2:
            print(f"[yellow]Skipping cluster {cluster_id}: not enough variation in {density_col}[/]")
            continue

        # Check for missing levels or malformed model
        try:
            # This tests the formula without running the model
            y, X = dmatrices(f"{density_col} ~ {formula}", data=sub, return_type='dataframe')
        except (PatsyError, ValueError) as e:
            print(f"[yellow]Skipping cluster {cluster_id}: error building model - {e}[/]")
            continue

        try:
            model = ols(f"{density_col} ~ {formula}", data=sub).fit()
            aov = sm.stats.anova_lm(model, typ=2)  # Assumes a balanced design with data for all clusters
        except Exception as e:
            print(f"[yellow]Skipping cluster {cluster_id}: ANOVA failed - {e}[/]")
            continue

        for aov_term in aov.index:
            if effect_of_interest and not match_effect(aov_term, effect_of_interest):
                continue
            pval = aov.loc[aov_term, 'PR(>F)']
            rows.append({
                'cluster_ID': cluster_id,
                'comparison': f"ANOVA: {aov_term}",
                'higher_mean_group': '',
                'p-value': pval,
                'significance': '****' if pval < 0.0001 else '***' if pval < 0.001 else '**' if pval < 0.01 else '*' if pval < 0.05 else 'n.s.'
            })

    return pd.DataFrame(rows)

def valid_clusters_dunnett_test(df, control_group, test_groups, density_col, direction='two-sided'):
    """
    Perform Dunnett's test across clusters, comparing multiple test groups to a single control.

    For each cluster, performs one-sided or two-sided t-tests between the control group and each test group,
    then applies Dunnett's correction for multiple comparisons. The maximum p-value across tests is reported.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing cluster-level data. Must include 'cluster_ID', 'condition', and the specified density column.
    control_group : str
        Name of the control group. Must appear only as the first group (not in test_groups).
    test_groups : list of str
        List of experimental groups to compare against the control group.
    density_col : str
        Name of the column containing the dependent variable (e.g., 'cell_density', 'label_density').
    direction : {'two-sided', 'less', 'greater'}, default='two-sided'
        Type of alternative hypothesis for the t-tests:
            - 'less': tests if control < test group
            - 'greater': tests if control > test group
            - 'two-sided': tests for any difference

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per cluster.
        Columns: ['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']

    Notes
    -----
    - Dunnett’s test adjusts for multiple comparisons between one control and multiple test groups.
    - All comparisons must show significance in the same direction for the cluster to be considered valid later.
    - The reported p-value is the maximum across all individual comparisons for that cluster.
    - 'higher_mean_group' is left blank, since the test does not directly identify the direction of the effect per group.
    - Significance levels are annotated as:
        * '****' if p < 0.0001
        * '***'  if p < 0.001
        * '**'   if p < 0.01
        * '*'    if p < 0.05
        * 'n.s.' otherwise
    - Clusters that cause errors (e.g., due to missing group data) are skipped with a warning.
    """

    stats_df = pd.DataFrame()

    for cluster_id in df['cluster_ID'].unique():
        sub_df = df[df['cluster_ID'] == cluster_id]

        control_vals = sub_df[sub_df['condition'] == control_group][density_col]
        test_vals = [sub_df[sub_df['condition'] == g][density_col] for g in test_groups]

        try:
            res = dunnett(*test_vals, control=control_vals, alternative=direction)
        except Exception as e:
            print(f"[warning] Skipping cluster {cluster_id} due to error: {e}")
            continue

        max_p = max(res.pvalue)
        stats_df = pd.concat([
            stats_df,
            pd.DataFrame({
                'cluster_ID': [cluster_id],
                'comparison': [f"Dunnett: {control_group} vs {','.join(test_groups)}"],
                'higher_mean_group': [''],  # Leave blank for now
                'p-value': [max_p],
                'significance': ['****' if max_p < 0.0001 else '***' if max_p < 0.001 else '**' if max_p < 0.01 else '*' if max_p < 0.05 else 'n.s.']
            })
        ], ignore_index=True)
    return stats_df

def valid_clusters_holm_sidak(df, comparisons, density_col):
    """
    Perform multiple two-sided t-tests with Holm–Šidák correction across clusters.

    For each cluster, performs all specified pairwise comparisons between groups using unpaired
    two-sided t-tests. P-values are adjusted for multiple comparisons using the Holm–Šidák method.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing cluster-level data. Must include 'cluster_ID', 'condition', and the specified density column.
    comparisons : list of tuple
        List of comparisons in the format (group1, group2, direction), where 'direction' is ignored
        (always two-sided tests are used here).
    density_col : str
        Name of the column containing the dependent variable (e.g., 'cell_density', 'label_density').

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per cluster per comparison.
        Columns: ['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']

    Notes
    -----
    - The Holm–Šidák correction controls the family-wise error rate across multiple pairwise comparisons.
    - Comparisons are always two-sided, regardless of any directional input in the comparisons list.
    - 'higher_mean_group' indicates which group had the higher mean (only filled if the test is significant).
    - Significance levels are annotated as:
        * '***' if p < 0.001
        * '**'  if p < 0.01
        * '*'   if p < 0.05
        * 'n.s.' otherwise
    - Clusters with insufficient data in any group may yield unreliable results; no explicit filtering is applied.
    - This test is useful when there is no shared control group and comparisons are arbitrary.
    """
    results = []
    for cluster_id in df['cluster_ID'].unique():
        pvals = []
        comp_names = []
        higher_means = []
        for g1, g2, _ in comparisons:
            vals1 = df[(df['cluster_ID'] == cluster_id) & (df['condition'] == g1)][density_col]
            vals2 = df[(df['cluster_ID'] == cluster_id) & (df['condition'] == g2)][density_col]
            t, p = ttest_ind(vals1, vals2, equal_var=True, alternative='two-sided')
            pvals.append(p)
            comp_names.append(f"{g1} vs {g2}")
            higher_means.append(g1 if vals1.mean() > vals2.mean() else g2)

        reject, pvals_corr, _, _ = multipletests(pvals, alpha=0.05, method='holm-sidak')
        for i in range(len(pvals)):
            results.append({
                'cluster_ID': cluster_id,
                'comparison': comp_names[i],
                'higher_mean_group': higher_means[i] if reject[i] else '',
                'p-value': pvals_corr[i],
                'significance': '***' if pvals_corr[i] < 0.001 else '**' if pvals_corr[i] < 0.01 else '*' if pvals_corr[i] < 0.05 else 'n.s.'
            })

    results_df = pd.DataFrame(results)
    return results_df

def valid_clusters_tukey_test(df, density_col):
    """
    Perform Tukey's HSD test for each cluster and return the multiple comparison results.

    For each unique cluster_ID, this function compares all group pairs using Tukey’s
    Honestly Significant Difference (HSD) test. The group with the higher mean is reported
    along with adjusted p-values and significance levels.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing cluster-level data. Must include:
            - 'cluster_ID': unique cluster identifiers
            - 'condition': group labels (e.g., treatment groups)
            - The specified density column (e.g., 'cell_density' or 'label_density')
    density_col : str
        Name of the column containing the dependent variable to test.

    Returns
    -------
    stats_df : pd.DataFrame
        DataFrame containing Tukey's test results for each cluster and pairwise group comparison.
        Columns:
            - 'cluster_ID': the cluster being tested
            - 'comparison': formatted as "Group1 vs Group2"
            - 'higher_mean_group': the group with the higher mean
            - 'p-value': adjusted p-value for the comparison
            - 'significance': significance annotation based on the p-value

    Notes
    -----
    - Tukey’s HSD test performs all pairwise comparisons between groups and controls the family-wise error rate.
    - The group with the higher mean is inferred from the sign of the `meandiff` in the Tukey results.
    - P-values are adjusted automatically and mapped to the following significance levels:
        * '****' if p < 0.0001
        * '***'  if p < 0.001
        * '**'   if p < 0.01
        * '*'    if p < 0.05
        * 'n.s.' otherwise
    - Progress is displayed using a Rich live progress bar.
    - Clusters with no data are skipped.
    """

    stats_df = pd.DataFrame()
    progress, task_id = initialize_progress_bar(len(df['cluster_ID'].unique()), "[default]Processing clusters...")
    with Live(progress):
        for cluster_id in df['cluster_ID'].unique():
            cluster_data = df[df['cluster_ID'] == cluster_id]
            if not cluster_data.empty:
                # Flatten the data
                densities = np.array([value for value in cluster_data[density_col].values.ravel()])
                group_labels = np.array([value for value in cluster_data['condition'].values.ravel()])

                # Perform Tukey's HSD test
                tukey_results = pairwise_tukeyhsd(endog=densities, groups=group_labels, alpha=0.05)

                # Extract significant comparisons from Tukey's results 
                # Columns: group1, group2, meandiff, p-adj, lower, upper, reject, cluster_ID
                test_results_df = pd.DataFrame(data=tukey_results.summary().data[1:], columns=tukey_results.summary().data[0])

                # Add the cluster ID to the DataFrame
                test_results_df['cluster_ID'] = cluster_id

                # Add a column for the group with the higher mean density
                test_results_df['higher_mean_group'] = test_results_df.apply(lambda row: row['group1'] if row['meandiff'] < 0 else row['group2'], axis=1)

                # Append the current test results to the overall DataFrame 
                stats_df = pd.concat([stats_df, test_results_df], ignore_index=True)

            progress.update(task_id, advance=1)

    # Update columns
    stats_df.rename(columns={'p-adj': 'p-value'}, inplace=True)
    stats_df['comparison'] = stats_df['group1'] + ' vs ' + stats_df['group2']
    stats_df.drop(columns=['lower', 'upper', 'reject', 'meandiff', 'group1', 'group2'], inplace=True)
    stats_df['significance'] = stats_df['p-value'].apply(lambda p: '****' if p < 0.0001 else '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.')
    stats_df = stats_df[['cluster_ID', 'comparison', 'higher_mean_group', 'p-value', 'significance']]

    return stats_df 

def cluster_validation_data_df(density_col, has_hemisphere, csv_files, groups, data_col, data_col_pooled):
    """
    Aggregate cluster-level data from .csv files, optionally pooling across hemispheres.

    This function loads per-sample cluster data from CSV files, filters by specified groups,
    and optionally pools bilateral data (if LH/RH hemisphere files are detected). It returns
    a unified DataFrame suitable for statistical analysis.

    Parameters
    ----------
    density_col : str
        Name of the column containing the density values (e.g., 'cell_density', 'label_density').
    has_hemisphere : bool
        Whether the input files contain hemisphere-specific suffixes (e.g., _LH.csv or _RH.csv).
        If True, hemisphere-specific data will be summed per sample.
    csv_files : list of Path
        List of input CSV files containing cluster-wise data.
    groups : list of str
        List of group/condition names to include (e.g., ['saline', 'MDMA']).
    data_col : str
        Name of the raw count/volume column to pool (e.g., 'cell_count' or 'label_volume').
    data_col_pooled : str
        Name of the pooled column to create (e.g., 'pooled_cell_count').

    Returns
    -------
    data_df : pd.DataFrame
        Aggregated DataFrame with cluster-level data ready for analysis.
        For bilateral data (has_hemisphere=True), columns include:
            - 'condition', 'sample', 'cluster_ID', pooled counts/volume, pooled cluster volume, and density.
        For unilateral data, the same columns are returned, excluding pooling.

    Notes
    -----
    - Files must include columns like: 'sample', 'cluster_ID', data_col, 'cluster_volume',
      and optionally bounding box coordinates ('xmin', 'xmax', etc.), which are dropped.
    - Hemisphere data is pooled by summing values across LH and RH files per sample.
    - Group filtering is based on the prefix of the file name (e.g., 'saline_sample01.csv' → group = 'saline').
    - Only files matching one of the specified groups are processed.
    """

    # Create a results dataframe
    data_df = pd.DataFrame(columns=['condition', 'sample', 'side', 'cluster_ID', data_col, 'cluster_volume', density_col])

    if has_hemisphere:
        # Process files with hemisphere pooling
        print(f"Organizing [red1 bold]bilateral[/red1 bold] [dark_orange bold]{density_col}[/] data from [orange1 bold]_LH.csv[/] and [orange1 bold]_RH.csv[/] files...")
        for file in csv_files:
            condition_name = str(file.name).split('_')[0]
            if condition_name in groups:
                side = str(file.name).split('_')[-1].split('.')[0]
                df = pd.read_csv(file)
                df = df.drop(columns=['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'])
                df['condition'] = condition_name  # Add the condition to the df
                df['side'] = side  # Add the side 
                data_df = pd.concat([data_df, df], ignore_index=True)

        # Pool data by condition, sample, and cluster_ID
        data_df = data_df.groupby(['condition', 'sample', 'cluster_ID']).agg(  # Group by condition, sample, and cluster_ID
            **{data_col_pooled: pd.NamedAgg(column=data_col, aggfunc='sum'),  # Sum cell_count or label_volume, unpacking the dict into keyword arguments for the .agg() method 
            'pooled_cluster_volume': pd.NamedAgg(column='cluster_volume', aggfunc='sum')}  # Sum cluster_volume
        ).reset_index() # Reset the index to avoid a multi-index dataframe

        data_df[density_col] = data_df[data_col_pooled] / data_df['pooled_cluster_volume']  # Add a column for cell/label density
    else:
        # Process files without hemisphere pooling
        print(f"Organizing [red1 bold]unilateral[/] [dark_orange bold]{density_col}[/] data...")
        for file in csv_files:
            df = pd.read_csv(file)
            condition_name = file.stem.split('_')[0]
            if condition_name in groups:
                df['condition'] = str(condition_name)
                df = df.drop(columns=[data_col, 'cluster_volume', 'xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'])
                data_df = pd.concat([data_df, df], ignore_index=True)

    return data_df

def determine_valid_clusters(stats_df, validation_criteria='all', cluster_col='cluster_ID'):
    """
    Determine valid clusters based on test type and significance criteria.

    Parameters
    ----------
    stats_df : pd.DataFrame
    test_type : str
    validation_criteria : str or int
        - 'all': all comparisons must be significant
        - 'any': at least one must be significant
        - int: at least N comparisons must be significant
    cluster_col : str
    """
    valid_clusters = []
    for cluster_id, group_df in stats_df.groupby(cluster_col):
        n_sig = (group_df['significance'] != 'n.s.').sum()

        if validation_criteria == 'all':
            if n_sig == len(group_df):
                valid_clusters.append(cluster_id)
        elif validation_criteria == 'any':
            if n_sig >= 1:
                valid_clusters.append(cluster_id)
        else:
            try:
                validation_criteria_n = int(validation_criteria)
                if n_sig >= validation_criteria_n:
                    valid_clusters.append(cluster_id)
            except ValueError:
                raise ValueError(f"Invalid --validation_criteria value: {validation_criteria}")
    return valid_clusters


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Validation logic
    val_crit = int(args.val_crit) if args.val_crit.isdigit() else args.val_crit.lower()
    if val_crit not in {'all', 'any'} and not isinstance(val_crit, int):
        print('[red]--val_crit must be a number, "all", or "any".[/]')
        return
    
    # Enforce mutually exclusive modes of validation: either comparisons OR ANOVA (group_map + formula)
    using_anova = args.group_map is not None or args.formula is not None
    using_comparisons = args.comparisons and args.comparisons != ['all']

    if using_anova and using_comparisons:
        print("[red]Error: Use either --comparisons or both --group_map and --formula, not both.[/]")
        return
    elif using_anova and not (args.group_map and args.formula):
        print("[red]Error: Both --group_map and --formula are required together.[/]")
        return

    cwd = Path.cwd()
    subdirs = [d for d in cwd.iterdir() if d.is_dir() and d.name != '_valid_clusters_stats']
    if not subdirs:
        print('[red]No subdirectories found to process.[/]')
        return

    # Iterate over all subdirectories in the current working directory
    for subdir in subdirs:
        print(f"\n[bold]Processing directory:[/] {subdir.name}")

        # Load all .csv files in the current subdirectory
        csv_files = match_files('*.csv', subdir)
        if not csv_files:
            print(f"[yellow]No CSV files found in {subdir}[/]")
            continue  # Skip directories with no CSV files

        # Make output dir
        output_dir = subdir / '_valid_clusters_stats'
        output_dir.mkdir(exist_ok=True)

        # Skip processing if expected files are present
        expected_files = [
            output_dir.glob('*_results.csv'),
            output_dir.glob('valid_cluster_IDs_*.txt'),
            output_dir.glob('cluster_validation_info_*.csv'),
        ]

        if not args.overwrite and all(any(files) for files in expected_files): # e.g., checks if tukey_results.csv, valid_cluster_IDs_tukey.txt, and cluster_validation_info_tukey.csv exist
            print(f"[green]Skipping {subdir.name} – output already exists. Use --overwrite to force reprocessing.")
            continue

        # Load the first .csv file to check for data columns and set the appropriate column names
        first_df = pd.read_csv(csv_files[0])
        if 'cell_count' in first_df.columns:
            data_col, data_col_pooled, density_col = 'cell_count', 'pooled_cell_count', 'cell_density'
        elif 'label_volume' in first_df.columns:
            data_col, data_col_pooled, density_col = 'label_volume', 'pooled_label_volume', 'label_density'
        else:
            print("[red1]Error: Input CSVs lack recognized data columns.")
            continue
        
        # Get the total number of clusters before filtering out non-significant clusters
        total_clusters = first_df['cluster_ID'].nunique()

        # Check if any files contain hemisphere indicators
        has_hemisphere = any('_LH.csv' in str(f.name) or '_RH.csv' in str(f.name) for f in csv_files)

        # Parse comparisons or main effect
        comparisons = None
        if args.comparisons:
            all_conditions = sorted(set(f.name.split('_')[0] for f in csv_files))
            comparisons = parse_comparisons(args.comparisons, all_conditions)
            groups = sorted(set(g for c in comparisons for g in c[:2]))
            if args.comparisons == ['all']:
                test_type = 'tukey'
            elif len(comparisons) == 1:
                test_type = 't-test'
            elif all(g1 == comparisons[0][0] for g1, _, _ in comparisons):
                test_type = 'dunnett'
            else:
                test_type = 'holm'
        elif args.group_map and args.formula:
            test_type = 'anova'
            group_map = pd.read_csv(args.group_map)
            if 'condition' not in group_map.columns:
                print('[red]group_map CSV must include a "condition" column.[/]')
                continue
            formula = args.formula.replace(" ", "")
            factor_cols = [f.strip() for f in formula.replace('*', '+').split('+')]
            missing_cols = [col for col in factor_cols if col not in group_map.columns]
            if missing_cols:
                print(f'[red]Missing factor columns in group_map: {missing_cols}[/]')
                continue
            groups = group_map['condition'].unique().tolist()
        else:
            print('[red]You must provide either --comparisons or both --group_map and --formula for ANOVA.[/]')
            continue
    
        # Aggregate the data from all .csv files and pool the data if hemispheres are present
        data_df = cluster_validation_data_df(
            density_col=density_col,
            has_hemisphere=has_hemisphere,
            csv_files=csv_files,
            groups=groups,
            data_col=data_col,
            data_col_pooled=data_col_pooled
        )

        if data_df.empty:
            print("[red1]No matching data found for specified groups.")
            continue

        # Run selected test
        if test_type == 'anova':
            data_df = data_df.merge(group_map, on='condition', how='left')
            if data_df.isnull().any().any():
                print('[red]One or more conditions in the CSVs are not present in the group_map.[/]')
                continue

            # Automatically cast string-based columns in factor_cols to category
            for col in factor_cols:
                if data_df[col].dtype == object or pd.api.types.is_string_dtype(data_df[col]):
                    data_df[col] = data_df[col].astype('category')

            stats_df = valid_clusters_anova(data_df, density_col, formula, effect_of_interest=args.effect)

        elif test_type == 'tukey':
            print("[bold gold1]Running Tukey's HSD[/] across all groups")
            stats_df = valid_clusters_tukey_test(data_df, density_col)
        elif test_type == 'dunnett':
            control_group = comparisons[0][0]  # First group in the first comparison is the control
            test_groups = [g2 for g1, g2, _ in comparisons if g1 == control_group]
            print(f"[bold gold1]Running Dunnett's test[/] with control: [cyan]{control_group}[/]")
            stats_df = valid_clusters_dunnett_test(data_df, control_group, test_groups, density_col)
        elif test_type == 'holm':
            print("[bold gold1]Running Holm–Šidák corrected t-tests[/]")
            stats_df = valid_clusters_holm_sidak(data_df, comparisons, density_col)
        elif test_type == 't-test':
            g1, g2, direction = comparisons[0]
            print(f"[bold gold1]Running t-test:[/] [cyan]{g1} {direction} {g2}[/]")
            stats_df = valid_clusters_t_test(data_df, g1, g2, density_col, alternative=direction)
        else:
            print("[red1]Invalid test_type detected.")
            continue

        # Warn if val_crit exceeds number of comparisons
        max_comparisons = stats_df.groupby('cluster_ID').size().max()
        if isinstance(val_crit, int) and val_crit > max_comparisons:
            print(f"[yellow]Warning: --val_crit={val_crit} exceeds number of comparisons per cluster ({max_comparisons}). No clusters will pass.")

        # Determine valid clusters
        valid_ids = determine_valid_clusters(stats_df, validation_criteria=val_crit)
        valid_ids_str = ' '.join(map(str, valid_ids))

        # Load p-threshold from file
        p_val_file = next(subdir.rglob(args.p_val_txt), None)
        if p_val_file is None:
            print(f"[red1]Missing p-value file: {args.p_val_txt}")
            continue
        p_thresh = float(p_val_file.read_text().strip())

        # Save results
        tag = test_type
        raw_prefix = output_dir / f'raw_data_for_{tag}'
        raw_path = raw_prefix.with_suffix('_pooled.csv') if has_hemisphere else raw_prefix.with_suffix('.csv')
        stats_path = output_dir / f'{tag}_results.csv'
        ids_path = output_dir / f'valid_cluster_IDs_{tag}.txt'
        info_path = output_dir / f'cluster_validation_info_{tag}.csv'

        data_df.to_csv(raw_path, index=False)
        stats_df.to_csv(stats_path, index=False)
        with open(ids_path, 'w') as f:
            f.write(valid_ids_str)

        # Extract the FDR q value from the first csv file (float after 'FDR' or 'q' in the file name)
        first_csv_name = csv_files[0]
        if 'FDR' in first_csv_name.name or 'q' in first_csv_name.name:
            fdr_q = float(str(first_csv_name).split('FDR')[-1].split('q')[-1].split('_')[0])
        else:
            fdr_q = None  # No FDR/q value found

        # Print validation info
        print(f"\n[bold green]Validation complete for {subdir.name}[/]")
        if fdr_q is not None:
            print(f"FDR q: [cyan bold]{fdr_q}[/] == p-value threshold: [cyan bold]{p_thresh}")
        else:
            print(f"P-value threshold: [cyan bold]{p_thresh}")
        print(f"Valid cluster IDs: [cyan]{valid_ids_str}")
        print(f"[default]# of valid / total #: [bright_magenta]{len(valid_ids)} / {total_clusters}")
        validation_rate = len(valid_ids) / total_clusters * 100
        print(f"Cluster validation rate: [purple bold]{validation_rate:.2f}%")

        # Save the number of significant clusters, total clusters, and validation rate to a .txt file
        validation_inf_txt = output_dir / f'cluster_validation_info_{tag}.txt'
        with open(validation_inf_txt, 'w') as f:
            f.write(f"Validation criteria: {val_crit}\n")
            if fdr_q is not None:
                f.write(f"FDR q: {fdr_q} == p-value threshold {p_thresh}\n")
            else:
                f.write(f"P-value threshold: {p_thresh}\n")
            f.write(f"Valid cluster IDs: {valid_ids_str}\n")
            f.write(f"# of valid / total #: {len(valid_ids)} / {total_clusters}\n")
            f.write(f"Cluster validation rate: {validation_rate:.2f}%\n")

        pd.DataFrame({
            'Validation criteria': [args.comparisons or args.effect],
            'Test type': [test_type],
            'P value thresh': [p_thresh],
            'Valid clusters': [valid_ids_str],
            '# of valid clusters': [len(valid_ids)],
            '# of clusters': [total_clusters],
            'Validation rate': [f"{validation_rate:.2f}%"],
            'FDR q': fdr_q
        }).to_csv(info_path, index=False)

    # Merge validation summaries
    for tag in ['t-test', 'holm', 'dunnett', 'tukey', 'anova']:
        files = list(Path.cwd().rglob(f'*/_valid_clusters_stats/cluster_validation_info_{tag}.csv'))
        if files:
            # Concat all validation info files into a single summary file
            cluster_summary(f'cluster_validation_info_{tag}.csv', f'cluster_validation_summary_{tag}.csv')

    verbose_end_msg()


if __name__ == '__main__':
    main()