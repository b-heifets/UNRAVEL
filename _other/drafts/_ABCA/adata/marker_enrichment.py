#!/usr/bin/env python3

"""
Use ``marker_enrichment`` from UNRAVEL to load a scRNA-seq expression CSV file and calculate marker gene enrichment for specified genes.

Note:
    - The enrichment is calculated for each gene and cell type (mean expression in cell type / mean expression overall).
    - For combos of genes, use comma-separated values without spaces (e.g., GeneA,GeneB).
    - Example: Gene1 Gene2,Gene3 Gene4
    - With gene combos, the enrichment is calculated as the mean of the individual gene enrichments
    - The selected cell type column is then sorted by the highest enrichment across all genes or gene combos.
    - Markers for each mouse cell type are available in Supplementary Table 7 from Yao et al., (2023): 
    - https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-023-06812-z/MediaObjects/41586_2023_6812_MOESM8_ESM.xlsx
"""

from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input CSV file.', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Single gene or comma-separated combo (e.g., CALB2 or CALB2,RBP4).', required=True, action=SM)
    reqs.add_argument('-c', '--column', help='Cell type column to calculate enrichment for (neurotransmitter, class, subclass, supertype, cluster, supercluster, subcluster).', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: mouse', default='mouse', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def normalize_gene_names(gene_list: List[str], species: str) -> List[str]: # This could be imported once integrated elsewhere
    """Normalize gene names based on species conventions."""
    if species == 'mouse':
        # Mouse gene symbols: capitalize only the first letter (Htr2a)
        gene_list = [g.lower().capitalize() for g in gene_list]
    elif species == 'human':
        # Human gene symbols: all uppercase (HTR2A)
        gene_list = [g.upper() for g in gene_list]
    return gene_list

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the CSV file
    print(f"\nLoading key data from [bold]{args.input}[/bold]...\n")
    input_path = Path(args.input)
    cols = pd.read_csv(args.input, nrows=0).columns
    if args.column not in cols:
        raise ValueError(f"Selected column '{args.column}' not found in input data columns.")
    gene_list = normalize_gene_names(args.genes.split(','), species=args.species)
    for gene in gene_list:
        if gene not in cols:
            raise ValueError(f"Gene '{gene}' not found in input data columns.")
    use = [args.column] + gene_list    
    df = pd.read_csv(input_path, usecols=use)

    # Make the args.column the first column
    cols = df.columns.tolist()
    cols.insert(0, cols.pop(cols.index(args.column)))
    df = df[cols]

    print(df)

    if ',' in args.genes:
        print(f"\nCalculating marker enrichment for gene combo: {gene_list}\n")
    else:
        print(f"\nCalculating marker enrichment for gene: {gene_list[0]}\n")

    # Print all expression values for Drd1 for the '018 L2 IT PPP-APr Glut' subclass
    gene_values = df[df[args.column] == '018 L2 IT PPP-APr Glut']
    print(gene_values.head(100))
    # import sys ; sys.exit()

    # Calculate marker gene enrichment (mean for a cell type / mean for all cell types in the cell type column)
    group_means = df.groupby(args.column).mean(numeric_only=True)

    print(f"\nGroup means:\n{group_means}\n")

    # Print this for the subclass: '018 L2 IT PPP-APr Glut'
    print(f"\nMean expression for '018 L2 IT PPP-APr Glut':\n{group_means.loc['018 L2 IT PPP-APr Glut']}\n")

    overall_means = df.mean(numeric_only=True)

    print(f"\nOverall means:\n{overall_means}\n")
    # import sys ; sys.exit()

    enrichment_values = []
    for cell_type, row in group_means.iterrows():
        mean_in_type = row[gene_list].mean()
        mean_overall = overall_means[gene_list].mean()
        enrichment = mean_in_type / mean_overall if mean_overall != 0 else np.nan
        enrichment_values.append({'cell_type': cell_type, 'enrichment': enrichment})

    enrichment_df = pd.DataFrame(enrichment_values).sort_values('enrichment', ascending=False)

    print(enrichment_df)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        gene_tag = args.gene.replace(',', '_')
        output_filename = f"{input_path.stem}_{args.column}_marker_enrichment_{gene_tag}.csv"
        output_path = input_path.parent / output_filename
    enrichment_df.to_csv(output_path, index=False)
    print(f"\nSaved enrichment table to [bold]{output_path}[/bold]\n")

    print(enrichment_df)
    verbose_end_msg()

if __name__ == '__main__':
    main()
