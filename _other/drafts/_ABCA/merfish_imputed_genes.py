#!/usr/bin/env python3

"""
Use ``/Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_imputed_gnes.py`` from UNRAVEL to list imputed genes from the Allen Brain Cell Atlas MERFISH data.

Note:
    - https://alleninstitute.github.io/abc_atlas_access/notebooks/merfish_ccf_registration_tutorial.html#read-in-section-reconstructed-and-ccf-coordinates-for-all-cells

Usage for gene:
---------------
    merfish_imputed_genes.py -b path/to/root_dir
"""

import anndata
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Make this script more general by allowing the user to specify the path to the expression data file. 

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    expression_path = download_base / 'expression_matrices/MERFISH-C57BL6J-638850-imputed/20240831/C57BL6J-638850-imputed-log2.h5ad'

    print(f"\n    Loading expression data from {expression_path}\n")

    adata = anndata.read_h5ad(expression_path, backed='r')
    
    # Get list of genes (var) in the expression data
    genes = adata.var.gene_symbol

    print(f'\nImputed genes: \n')

    for gene in genes:
        print(f"'{gene}'delimiter")

    verbose_end_msg()


if __name__ == '__main__':
    main()