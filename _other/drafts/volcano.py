#!/usr/bin/env python3

"""
Use volcano.py from UNRAVEL to create a volcano plot.

Input: 
    - path/.csv
    - Expected column order: label, effect size, p-value (names can vary)
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from adjustText import adjust_text
from pathlib import Path
from rich import print
from rich.traceback import install
from statsmodels.stats.multitest import multipletests

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/.csv', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-t', '--title', help='Title for the plot. Default: "Volcano Plot".', default='Volcano Plot', action=SM)
    opts.add_argument('-p', '--top_percent_pos', help='Top percent of significant points to label for positive effects. Default: 10.', type=float, default=10, action=SM)
    opts.add_argument('-n', '--top_percent_neg', help='Top percent of significant points to label for negative effects. Default: 10.', type=float, default=10, action=SM)
    opts.add_argument('-x', '--per_x_range', help='Percentage of x-axis range for random label offset. Default: 0.01.', type=float, default=0.01, action=SM)
    opts.add_argument('-y', '--per_y_range', help='Percentage of y-axis range for random label offset. Default: 0.08.', type=float, default=0.08, action=SM)
    opts.add_argument('-th', '--thresh_type', help='For point labeling, threshold sig. and/or effect size. Default: "and".', choices=['and', 'or'], default='and', action=SM)
    
    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the CSV file
    df = pd.read_csv(args.input)
    cols = df.columns

    # Step 2: Create the Volcano Plot
    plt.figure(figsize=(12, 10))

    # Plot all points, color by significance
    plt.scatter(df[cols[1]], df[cols[2]], c='grey', label='Not significant', alpha=0.5)

    # Check types of all columns
    print(f"\n{df.dtypes=}/n")

    # Plot significant points: red for r > 0, blue for r < 0
    significant = df[cols[2]] > -np.log10(0.05)
    plt.scatter(df.loc[significant & (df[cols[1]] > 0), cols[1]], 
                df.loc[significant & (df[cols[1]] > 0), cols[2]], 
                c='red', label='Significant (x var. > 0)', edgecolor='grey', alpha=0.5)
    plt.scatter(df.loc[significant & (df[cols[1]] < 0), cols[1]], 
                df.loc[significant & (df[cols[1]] < 0), cols[2]], 
                c='blue', label='Significant (x var. < 0)', edgecolor='grey', alpha=0.5)

    # Filter significant points
    sig_pos = df[significant & (df[cols[1]] > 0)]  # Significant positive effects
    sig_neg = df[significant & (df[cols[1]] < 0)]  # Significant negative effects

    print(f'\n{sig_pos=}\n')
    print(f'\n{sig_neg=}\n')

    # Check if sig_pos is not empty before calculating percentiles
    if not sig_pos.empty:
        percentile_pos = 100 - args.top_percent_pos
        effect_threshold_pos = np.percentile(sig_pos[cols[1]], percentile_pos)  # Top 10% positive effect size
        sig_threshold_pos = np.percentile(sig_pos[cols[2]], percentile_pos)  # Top 10% significance for positive effects
    else:
        effect_threshold_pos = None
        sig_threshold_pos = None

    # Check if sig_neg is not empty before calculating percentiles
    if not sig_neg.empty:
        percentile_neg = 100 - args.top_percent_neg
        effect_threshold_neg = np.percentile(sig_neg[cols[1]].abs(), percentile_neg)  # Top 10% negative effect size (absolute value)
        sig_threshold_neg = np.percentile(sig_neg[cols[2]], percentile_neg)  # Top 10% significance for negative effects
    else:
        effect_threshold_neg = None
        sig_threshold_neg = None

    # Only filter top points if thresholds are available
    if effect_threshold_pos is not None and sig_threshold_pos is not None:
        if args.thresh_type == 'or':
            top_pos = sig_pos[(sig_pos[cols[1]] >= effect_threshold_pos) | (sig_pos[cols[2]] >= sig_threshold_pos)]
        else:
            top_pos = sig_pos[(sig_pos[cols[1]] >= effect_threshold_pos) & (sig_pos[cols[2]] >= sig_threshold_pos)]
    else:
        top_pos = pd.DataFrame(columns=sig_pos.columns)

    if effect_threshold_neg is not None and sig_threshold_neg is not None:
        if args.thresh_type == 'or':
            top_neg = sig_neg[(sig_neg[cols[1]].abs() >= effect_threshold_neg) & (sig_neg[cols[2]] >= sig_threshold_neg)]
        else:
            top_neg = sig_neg[(sig_neg[cols[1]].abs() >= effect_threshold_neg) & (sig_neg[cols[2]] >= sig_threshold_neg)]
    else:
        top_neg = pd.DataFrame(columns=sig_neg.columns)

    print(f'\n{top_pos=}\n')
    print(f'\n{top_neg=}\n')

    # Get the current axis limits
    x_min, x_max = plt.gca().get_xlim()
    y_min, y_max = plt.gca().get_ylim()

    # Calculate the offset range as a fraction of the axis range for better label placement
    x_offset_range = (x_max - x_min) * args.per_x_range
    y_offset_range = (y_max - y_min) * args.per_y_range

    # Label these points with random x and y offsets based on axis ranges
    texts = []
    if not pd.concat([top_pos, top_neg]).empty:

        for _, row in pd.concat([top_pos, top_neg]).iterrows():
            # Generate random offsets within the calculated range
            rand_val_x = np.random.uniform(-x_offset_range, x_offset_range)  # Random x offset
            rand_val_y = np.random.uniform(-y_offset_range, y_offset_range)  # Random y offset

            # Apply the random offsets to the label position
            text = plt.text(row[cols[1]] + rand_val_x, row[cols[2]] + rand_val_y, row[cols[0]], fontsize=8)
            texts.append(text)

        # Adjust text to avoid overlap
        adjust_text(
            texts,
            # x=[row[cols[1]] for _, row in pd.concat([top_pos, top_neg]).iterrows()],
            # y=[row[cols[2]] for _, row in pd.concat([top_pos, top_neg]).iterrows()],
            force_text=(rand_val_x, rand_val_y),  # Adjust repel force for labels
            # force_static=(rand_val_x, rand_val_y),  # Adjust repel force for points
            ensure_inside_axes=True,  # Keep labels inside plot boundaries
        )
    else:
        print('No significant points to label.')


    # Add threshold line, labels, and legend
    plt.axhline(y=-np.log10(0.05), color='grey', linestyle='--', linewidth=0.7, label='FDR p < 0.05')
    plt.xlabel(cols[1])
    plt.ylabel('-log10(FDR-adjusted p-value)')
    plt.title(args.title)
    plt.legend()
    plt.ylim(0, plt.gca().get_ylim()[1] * 1.1)  # Extend y-axis slightly for better visibility

    # Save as PDF
    output = Path(args.input).with_suffix('.pdf')
    plt.savefig(output, format='pdf')

    plt.show()

    verbose_end_msg()

if __name__ == '__main__':
    main()
