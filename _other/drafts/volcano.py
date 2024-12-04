#!/usr/bin/env python3

"""
Use volcano.py from UNRAVEL to create a volcano plot.

Input: 
    - path/.csv
    - Column order: label, value, p-value (names can be different)
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
    reqs.add_argument('-l', '--label', help='Column name for labels (e.g., gene names)', required=True)
    reqs.add_argument('-val', '--value', help='Column name for correlation values', required=True)
    reqs.add_argument('-p', '--pvalue', help='Column name for p-values', required=True)
    
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

    # Rename columns to standard names for easier handling
    df = df.rename(columns={args.label: 'label', args.value: 'correlation', args.pvalue: 'p_value'})

    # Step 1: Apply FDR-BH correction
    df['p_adj'] = multipletests(df['p_value'], method='fdr_bh')[1]  # FDR-BH adjusted p-values
    df['log_p_adj'] = -np.log10(df['p_adj'])

    # Define significance threshold based on FDR-corrected p-value (e.g., FDR-adjusted p < 0.05)
    significant_threshold = -np.log10(0.05)

    # Step 2: Create the Volcano Plot
    plt.figure(figsize=(14, 8))

    # Plot all points, color by significance
    plt.scatter(df['correlation'], df['log_p_adj'], c='grey', label='Not significant')

    # Plot significant points: red for r >= 0, blue for r < 0
    significant = df['log_p_adj'] > significant_threshold
    plt.scatter(df.loc[significant & (df['correlation'] >= 0), 'correlation'], 
                df.loc[significant & (df['correlation'] >= 0), 'log_p_adj'], 
                c='red', label='Significant (r >= 0)', edgecolor='black')
    plt.scatter(df.loc[significant & (df['correlation'] < 0), 'correlation'], 
                df.loc[significant & (df['correlation'] < 0), 'log_p_adj'], 
                c='blue', label='Significant (r < 0)', edgecolor='black')

    # Step 3: Label the top 10 positive and top 10 negative correlations
    texts = []
    # Get the top 10 positive and top 10 negative significant correlations
    top_pos = df.loc[significant & (df['correlation'] > 0)].nlargest(10, 'correlation')
    top_neg = df.loc[significant & (df['correlation'] < 0)].nsmallest(10, 'correlation')
    
    # Label these points with a slight y-offset
    for _, row in pd.concat([top_pos, top_neg]).iterrows():
        text = plt.text(row['correlation'], row['log_p_adj'] + 0.2, row['label'], fontsize=8)  # Apply slight y-offset
        texts.append(text)

    # Adjust text to avoid overlap
    adjust_text(
        texts, 
        lim=50,                 # Allow some movement for text
        expand_text=(1.1, 1.1), # Slight expansion to avoid overlap
        expand_points=(1.2, 1.2), 
        force_text=1.2, 
        force_points=1.2
    )

    # Add threshold line, labels, and legend
    plt.axhline(y=significant_threshold, color='grey', linestyle='--', linewidth=0.7, label='FDR p < 0.05')
    plt.xlabel('Correlation')
    plt.ylabel('-log10(FDR-adjusted p-value)')
    plt.title('Volcano Plot of Gene Correlations with c-Fos Induction (FDR Corrected)')
    plt.legend()

    # Save as PDF
    output = Path(args.input).with_suffix('.pdf')
    plt.savefig(output, format='pdf')

    plt.show()

    verbose_end_msg()

if __name__ == '__main__':
    main()
