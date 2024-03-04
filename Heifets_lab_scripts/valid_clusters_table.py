#!/usr/bin/env python3

import argparse
from glob import glob
import numpy as np
import pandas as pd
from argparse_utils import SuppressMetavar, SM
from rich import print

def parse_args():
    parser = argparse.ArgumentParser(description='''Summarize volumes of the top x regions and collapsing them into parent regions until a criterion is met.''',
                                     formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/*_sunburst.csv. Default: first *_sunburst.csv match. Columns: Depth_0, Depth_1, ..., Volume_(mm^3)', action=SM)
    parser.add_argument('-s', '--sorted', help='path/*_sunburst_sorted.csv (default)', action=SM)
    parser.add_argument('-t', '--top_regions', help='Number of top regions to output. Default: 4', default=4, type=int, action=SM)
    parser.add_argument('-p', '--percent_vol', help='Percentage of the total volume the top regions must comprise [after collapsing]. Default: 0.8', default=0.8, type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Example usage:    top_regions.py -i input.csv

Sorting by heirarchy and volume: 
1) Group by Depth: Starting from the earliest depth column, for each depth level:
       - Sum the volumes of all rows sharing the same region (or combination of regions up to that depth).
       - Sort these groups by their aggregate volume in descending order, ensuring larger groups are prioritized.

2) Sort Within Groups: Within each group created in step 1:
       - Sort the rows by their individual volume in descending order.

3) Maintain Grouping Order: 
       - As we move to deeper depth levels, maintain the grouping and ordering established in previous steps
       (only adjusting the order within groups based on the new depth's aggregate volumes).  
    
"""
    return parser.parse_args()


def fill_na_with_last_known(df):
    depth_columns = [col for col in df.columns if 'Depth' in col]

    # Fill NaN with the last known non-NaN value within each row for depth columns
    df_filled = df.copy()
    df_filled[depth_columns] = df_filled[depth_columns].fillna(method='ffill', axis=1)

    return df_filled

def sort_sunburst_hierarchy(df):
    """Sort the DataFrame by hierarchy and volume."""

    depth_columns = [col for col in df.columns if 'Depth' in col]
    volume_column = 'Volume_(mm^3)'

    # For each depth, process groups and sort
    for i, depth in enumerate(depth_columns):
        # Temporary DataFrame to hold sorting results for each depth
        sorted_partial = pd.DataFrame()
        
        # Identify unique groups (rows) up to the current depth (e.g, if Depth_2, then root, grey, CH)
        unique_groups = df[depth_columns[:i + 1]].drop_duplicates()
        
        for _, group_values in unique_groups.iterrows():
            # Filter rows belonging to the current group
            mask = (df[depth_columns[:i + 1]] == group_values).all(axis=1) # Boolean series to check which rows == group_values
            group_df = df[mask].copy() # Apply mask to df to get a df for each group (copy to avoid SettingWithCopyWarning)
            
            # Calculate aggregate volume for the group and add it as a new column
            group_df.loc[:, 'aggregate_volume'] = group_df[volume_column].sum()

            # Sort the group by individual volume
            group_df = group_df.sort_values(by=[volume_column], ascending=False)
            
            # Append sorted group to the partial result
            sorted_partial = pd.concat([sorted_partial, group_df], axis=0)

        # Replace df with the sorted_partial for the next iteration
        df = sorted_partial.drop(columns=['aggregate_volume'])

    return df

def undo_fill_with_original(df_sorted, df_original):
    # Ensure the original DataFrame has not been altered; otherwise, use a saved copy before any modifications
    depth_columns = [col for col in df_original.columns if 'Depth' in col]
    
    # Use the index to replace filled values with original ones where NaN existed
    for column in depth_columns:
        df_sorted[column] = df_original.loc[df_sorted.index, column] # Use the index to replace filled values with original ones where NaN existed
    
    return df_sorted

def can_collapse(df, depth_col):
    """
    Determine if regions in the specified depth column can be collapsed.
    Returns a DataFrame with regions that can be collapsed based on volume and count criteria.
    """
    volume_column = 'Volume_(mm^3)'

    # Group by the parent region and aggregate both volume and count (.e.g, if a parent has 3 children, the count is 3)
    subregion_aggregates = df.groupby(depth_col).agg({volume_column: ['sum', 'count']})
    subregion_aggregates.columns = ['Volume_Sum', 'Count']

    # Adjust the condition to check for both a volume threshold and a minimum count of subregions
    pooling_potential = subregion_aggregates[(subregion_aggregates['Volume_Sum'] > 0) & (subregion_aggregates['Count'] > 1)]

    return pooling_potential # DataFrame with regions that can be collapsed based on volume and count criteria (Depth_*, Volume_Sum, Count)

def collapse_hierarchy(df, verbose=False):
    volume_column = 'Volume_(mm^3)'
    depth_columns = [col for col in df.columns if 'Depth' in col]

    for depth_level in reversed(range(len(depth_columns))):
        depth_col = depth_columns[depth_level]
        if depth_level == 0: break  # Stop if we're at the top level

        # Identify regions that can be collapsed into their parent
        collapsible_regions = can_collapse(df, depth_col)

        if verbose:
            print(f'\n{collapsible_regions=}\n')

        # If collapsible_regions is not empty, proceed with collapsing
        if not collapsible_regions.empty:
            
            # For each collapsible region name, get the name and the aggregate volume
            for region, row in collapsible_regions.iterrows():

                aggregated_volume = row['Volume_Sum']

                # Collapse rows containing the region name and set the volume to the aggregate volume
                df.loc[df[depth_col] == region, volume_column] = aggregated_volume

                # Set the child region name to NaN in the depth column using the depth level
                child_depth_col = depth_columns[depth_level + 1] 
                df.loc[df[depth_col] == region, child_depth_col] = np.nan    

                # Also set any subsequent depth columns to NaN
                for subsequent_depth_col in depth_columns[depth_level + 2:]:
                    df.loc[df[depth_col] == region, subsequent_depth_col] = np.nan
               

                # Remove duplicate rows for the collapsed region
                df = df.drop_duplicates()

            return df


def calculate_top_regions(df, top_n, percent_vol_threshold, verbose=False):
    """
    Identify the top regions based on the dynamically collapsed hierarchy,
    ensuring they meet the specified percentage volume criterion.
    
    :param df_collapsed: DataFrame with the hierarchy collapsed where meaningful.
    :param top_n: The number of top regions to identify.
    :param percent_vol_threshold: The minimum percentage of total volume these regions should represent.
    :return: DataFrame with the top regions and their volumes if the criterion is met; otherwise, None.
    """
    # Get the total volume
    total_volume = df['Volume_(mm^3)'].sum()

    # Get top regions
    df_sorted = df.sort_values(by='Volume_(mm^3)', ascending=False).reset_index(drop=True)
    top_regions_df = df_sorted.head(top_n)

    # Sum the volumes of the top regions
    top_regions_volume = top_regions_df['Volume_(mm^3)'].sum()

    # Calculate the percentage of the total volume the top regions represent
    percent_vol = top_regions_volume / total_volume

    if verbose:
        print(f'The percentage of the total volume the top {top_n} regions represents: {percent_vol}\n')

    # Check if the top regions meet the percentage volume criterion
    if percent_vol >= percent_vol_threshold:
        return top_regions_df
    else:
        return None


def main():
    args = parse_args()

    # Load the CSV file into a DataFrame
    if args.input:
        input_csv = args.input
    else:
        csv_files = glob('*sunburst.csv')
        input_csv = csv_files[0] # first match
    df = pd.read_csv(input_csv)

    # Fill NaN values in the original DataFrame
    df_filled_na = fill_na_with_last_known(df.copy())

    # Sort the DataFrame by hierarchy and volume
    df_filled_sorted = sort_sunburst_hierarchy(df_filled_na)

    # Undo the fill with the original values
    df_final = undo_fill_with_original(df_filled_sorted, df)

    # Save the sorted DataFrame to a new CSV file
    sorted_path = args.sorted if args.sorted else input_csv.replace('sunburst.csv', 'sunburst_sorted.csv')
    df_final.to_csv(sorted_path, index=False)

    if args.verbose:
        print(f'\nSunburst csv sorted by region hierarchy : \n')
        print(f'{df_final}\n')

    # Attempt to calculate top regions, collapsing as necessary
    criteria_met = False
    while not criteria_met:
        top_regions_df = calculate_top_regions(df_final, args.top_regions, args.percent_vol, args.verbose)

        if top_regions_df is not None and not top_regions_df.empty: # If top regions are found
            criteria_met = True

            # If a top region contributes to less than 1% of the total volume, remove it
            total_volume = df_final['Volume_(mm^3)'].sum()
            top_regions_df = top_regions_df[top_regions_df['Volume_(mm^3)'] / total_volume > 0.01]
            
            if args.verbose:
                print(f'\nTop regions meeting the volume criterion:\n')
                print(f'{top_regions_df}\n')

            # Initialize lists to hold the top region names and their aggregate volumes
            top_region_names_and_percent_vols = []

            # For each top region, get the region name and the aggregate volume
            for i, row in top_regions_df.iterrows():

                # Get the highest depth region name that is not NaN
                row_wo_volume = row[:10]
                region_name = row_wo_volume[::-1].dropna().iloc[0]

                # Calculate the percentage of the total volume the top regions represent
                aggregate_volume = row['Volume_(mm^3)']
                percent_vol = round(aggregate_volume / total_volume * 100)

                # Append the region name and the percentage volume to the list
                top_region_names_and_percent_vols.append(f'{region_name} ({percent_vol}%)')

            print(f'\n{total_volume=} mm^3')
            print(f'\n{top_region_names_and_percent_vols=}')

            # Save the top regions DataFrame to a new CSV file
            top_regions_path = args.sorted.replace('_sorted.csv', '_top_regions.csv') if args.sorted else input_csv.replace('sunburst.csv', 'sunburst_top_regions.csv')
            top_regions_df.to_csv(top_regions_path, index=False)
        else:
            # Attempt to collapse the hierarchy further
            df_final = collapse_hierarchy(df_final, args.verbose)

            if args.verbose:
                print(f'\nTop regions do not meet the volume criterion. Collapsing the hierarchy:\n')
                print(f'{df_final}\n')

            if df_final.empty:
                break  # Exit if no further collapsing is possible


if __name__ == '__main__':
    main()