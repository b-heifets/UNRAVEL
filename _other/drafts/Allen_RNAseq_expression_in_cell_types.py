#!/usr/bin/env python3

"""
Use ``./Allen_RNAseq_expression`` from UNRAVEL to extract expression data for specific genes from the Allen Brain Cell Atlas RNA-seq data.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/general_accessing_10x_snRNASeq_tutorial.htmlml

Usage:
------
    ./Allen_RNAseq_expression -b path/base_dir -g genes [-s mouse | human] [-c Neurons | Nonneurons] [-r region] [-d log2 | raw ] [-o output] [-v]

Usage for humans:
-----------------
    ./Allen_RNAseq_expression -b path/base_dir -g genes -c Neurons [-o output_dir] [-v]

Usage for mice:
---------------
    ./Allen_RNAseq_expression -b path/base_dir -g genes -r region [-o output_dir] [-v]
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from Allen_RNAseq_expression import load_RNAseq_cell_metadata, load_RNAseq_gene_metadata

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the MERFISH data', required=True, action=SM)
    reqs.add_argument('-i', '--input', help='path/gene_expression.csv', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to analyze', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: human', default='human', action=SM)

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

    cell_df = load_RNAseq_cell_metadata(download_base, species=args.species) # Add option to load cell_metadata_with_cluster_annotation.csv instead? Does this just add extra columns?

    # Load gene expression data
    gene_expression = pd.read_csv(args.input, index_col=0)

    # Join the cell metadata with the gene expression data
    gene_expression = gene_expression.join(cell_df)

    # Print the head of the joined data
    print(gene_expression.head())

    # Print all columns
    print(gene_expression.columns)

    # Print values of the first first row after the header
    print(gene_expression.iloc[0])


    verbose_end_msg()

if __name__ == '__main__':
    main()
