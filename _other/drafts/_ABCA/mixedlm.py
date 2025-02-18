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
    reqs.add_argument('-i', '--input', help='Path to the input CSV file (e.g., mixedlm.csv).', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-xn', '--x_names', help='Space-separated list of gene names for analysis. Default: all genes.', nargs='*', default=None, action=SM)
    opts.add_argument('-yn', '--y_name', help='Column name for the dependent variable (e.g., cFos). Default: cFos.', default='cFos', action=SM)
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

    # Load the input CSV
    try:
        df = pd.read_csv(args.input)
    except Exception as e:
        print(f"\n    [red]Error loading input CSV: {e}\n")
        return

    # Ensure required columns exist
    required_cols = ['Group', 'MouseID', 'RegionID', args.y_name]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"\n    [red]Error: Missing required columns in the CSV: {missing_cols}\n")
        return

    # If x_names is None, analyze all columns except metadata
    if not args.x_names:
        args.x_names = [col for col in df.columns if col not in required_cols]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Fit mixed models for each X variable
    summaries = []
    p_values = {}
    for x_name in args.x_names:
        if x_name not in df.columns:
            print(f"[yellow]Skipping {x_name}: Column not found in CSV.")
            continue

        print(f"\n[blue]Running mixed model for {args.y_name} ~ {x_name} * C(RegionID) * C(Group)...")
        try:
            model = smf.mixedlm(
                f"{args.y_name} ~ {x_name} * C(RegionID) * C(Group)",
                data=df,
                groups="MouseID",
                re_formula="~1"
            )
            result = model.fit()

            # Display the summary
            print(result.summary())

            # Store p-value for the interaction term
            interaction_term = f"{x_name}:C(RegionID):C(Group)"
            if interaction_term in result.pvalues:
                p_values[x_name] = result.pvalues[interaction_term]

            # Display and save the summary
            summaries.append(f"Model for {x_name}:\n{result.summary()}\n")

        except Exception as e:
            print(f"[red]Error fitting model for {x_name}: {e}")
            continue

    # Apply FDR correction if multiple genes are analyzed
    if len(p_values) > 1:
        print("\n[blue]Applying FDR correction to p-values...")
        genes = list(p_values.keys())
        pvals = list(p_values.values())

        # FDR correction
        _, fdr_corrected, _, _ = multipletests(pvals, alpha=args.fdr_threshold, method='fdr_bh')

        # Collect results
        fdr_results = pd.DataFrame({
            'Gene': genes,
            'Raw_p_value': pvals,
            'FDR_corrected_p_value': fdr_corrected
        })
        fdr_results['Significant'] = fdr_results['FDR_corrected_p_value'] < args.fdr_threshold

        print(fdr_results)

        # Save FDR results
        fdr_output_path = output_path.with_suffix('.fdr.csv')
        fdr_results.to_csv(fdr_output_path, index=False)
        print(f"\n    [green]FDR-corrected results saved to {fdr_output_path}\n")

    # Save all model summaries
    if summaries:
        with open(output_path, 'w') as file:
            file.writelines(summaries)
        print(f"\n    [green]Model summaries saved to {output_path}\n")
    else:
        print("\n    [yellow]No models were successfully fitted.\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()
