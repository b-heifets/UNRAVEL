#!/usr/bin/env python3

"""
Use ``mixedlm.py`` from UNRAVEL to run smf.mixedlm() analysis with region-wise intensities.

Inputs:
    - CSV with columns: Group, MouseID, RegionID, cFos, Gene1, Gene2, ...

Outputs:
    - Model summaries and optionally FDR-adjusted results.
    
Usage:
------
    mixedlm.py -i path/mixedlm.csv [-xn Gene1 Gene2 ...] [-yn cFos] [-q 0.05]
"""

import pandas as pd
import statsmodels.formula.api as smf
from pathlib import Path
from rich import print
from rich.traceback import install
from statsmodels.stats.multitest import multipletests


from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-x', '--x_vars_csv', help='path/merfish.csv.', required=True, action=SM)
    reqs.add_argument('-y', '--y_var_csv', help='path/lsfm.csv.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-xv', '--x_vars', help='Space-separated list of gene names for analysis. Default: all genes.', nargs='*', default=None, action=SM)
    opts.add_argument('-yv', '--y_var', help='Column name for the dependent variable (e.g., cFos). Default: cFos.', default='cFos', action=SM)
    opts.add_argument('-q', '--fdr_threshold', help='FDR correction threshold (q-value). Default: 0.05.', type=float, default=0.05, action=SM)
    opts.add_argument('-o', '--output', help='Path to save the model summaries. Default: results.txt.', default='results.txt', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    verbose_start_msg()

    # Load the CSVs
    x_vars_df = pd.read_csv(args.x_vars_csv)
    y_var_df = pd.read_csv(args.y_var_csv)

    # Merge on RegionID
    df = y_var_df.merge(x_vars_df, on="RegionID", how="left")

    # Sort by Group and MouseID
    df.sort_values(["Group", "MouseID"], inplace=True)

    print(df)

    # Rename columns to valid identifiers
    df.rename(columns=lambda x: f"gene_{x}" if x[0].isdigit() else x, inplace=True)

    print(df)

    # Ensure required columns exist
    required_cols = ['Group', 'MouseID', 'RegionID', args.y_var]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"\n    [red]Error: Missing required columns: {missing_cols}\n")
        return

    # If x_vars is None, analyze all columns except metadata
    if not args.x_vars:
        args.x_vars = [col for col in df.columns if col not in required_cols]

    # Fit mixed models for each X variable
    summaries = []
    for x_name in args.x_vars:
        if x_name not in df.columns:
            print(f"[yellow]Skipping {x_name}: Column not found in CSV.")
            continue

        formula = f"{args.y_var} ~ {x_name} + C(RegionID, Sum)"  # Effect coding for RegionID (the coefficients represent deviations from the overall mean)
        print(f"\n[blue]Running mixed model for {formula}...")
        model = smf.mixedlm(formula, data=df, groups="Group", re_formula="~1")  # Random intercepts for each group

        result = model.fit()

        # Display the summary
        print(result.summary())

        # Append the summary to the list
        summaries.append(f"\n\n{formula}\n{result.summary()}\n")

    # Save all model summaries
    if summaries:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as file:
            file.writelines(summaries)
        print(f"\n    [green]Model summaries saved to {output_path}\n")
    else:
        print("\n    [yellow]No models were successfully fitted.\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
