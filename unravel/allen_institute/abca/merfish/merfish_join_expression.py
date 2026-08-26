#!/usr/bin/env python3

"""
Use ``abca_merfish_join_expression`` (``mje``) from UNRAVEL to join [filtered] cell metadata with MERFISH expression data for a specified gene from the ABCA.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_tutorial_part_2b.html

Output:
    - A CSV file with the joined data (input_<gene>_expression.csv)

Usage:
------
    abca_merfish_join_expression -i path/filtered_cells.csv -b path/base_dir -g gene [-im] [-v]

"""

import anndata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import SimpleITK as sitk
from pathlib import Path
from rich import print
from rich.traceback import install

import unravel.allen_institute.abca.merfish.merfish as mf
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='path/filtered_cells.csv', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Genes to analyze', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-im', '--imputed', help='Use imputed expression data. Default: False', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Output path for the joined data. Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Load the filtered cell metadata
    cell_df = pd.read_csv(args.input, dtype={'cell_label': str})

    # Load the expression data for all genes (if the gene is in the dataset) 
    adata = mf.load_expression_data(download_base, args.genes, imputed=args.imputed)

    # Filter expression data for the specified genes
    asubset, gf = mf.filter_expression_data(adata, args.genes)

    # Create a dataframe with expression data
    gdata = asubset[:, gf.index].to_df()
    gdata.columns = gf['gene_symbol'].to_numpy()

    # Preserve the gene order supplied with --genes
    available_genes = set(gdata.columns)
    missing_genes = [gene for gene in args.genes if gene not in available_genes]
    ordered_genes = [gene for gene in args.genes if gene in available_genes]

    if missing_genes:
        print(
            f"[yellow]Warning: Genes not found and omitted: "
            f"{', '.join(missing_genes)}[/yellow]"
        )

    gdata = gdata.loc[:, ordered_genes]
        
    # exp_df = cell_df.join(gdata)  # Join the cell metadata with the expression data
    exp_df = cell_df.set_index('cell_label').join(gdata, how='left').reset_index()

    # Save the joined data
    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        first_gene = args.genes[0]
        if args.imputed:
            output_path = f"{Path(args.input).stem}_{first_gene}_imputed_expression.csv"
        else:
            output_path = f"{Path(args.input).stem}_{first_gene}_expression.csv"

    # Save the csv
    exp_df.to_csv(output_path, index=False)
    print(f"\n    Saved the joined data to {output_path}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()