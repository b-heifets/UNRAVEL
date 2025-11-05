#!/usr/bin/env python3
"""
Use ``abca_merfish_check_genes`` (alias ``mcg``) from UNRAVEL to check which of the specified genes 
are present in the regular and/or imputed MERFISH expression datasets from the Allen Brain Cell Atlas (ABCA).

Usage:
------
    abca_merfish_check_genes -g Slc32a1 Htr2a ... [-v]
"""

from typing import List
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
import unravel.allen_institute.abca.merfish.merfish as mf


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-g', '--genes', help='Space-separated list of gene symbols', required=True, nargs='*', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Could move lists of regular and imputed genes either to here or to a utils module.

def normalize_gene_names(gene_list: List[str], species: str) -> List[str]:
    """Normalize gene names based on species conventions."""
    if species == 'mouse':
        # Mouse gene symbols: capitalize only the first letter (Htr2a)
        return [g.lower().capitalize() for g in gene_list]
    elif species == 'human':
        # Human gene symbols: all uppercase (HTR2A)
        return [g.upper() for g in gene_list]
    return gene_list


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load available gene lists
    regular_genes = set(mf.genes_in_merfish_data())
    imputed_genes = set(mf.genes_in_imputed_merfish_data())

    gene_list = normalize_gene_names(args.genes, species='mouse')

    # Categorize
    in_regular = [g for g in gene_list if g in regular_genes]
    not_in_regular = [g for g in gene_list if g not in regular_genes]
    in_imputed_only = [g for g in not_in_regular if g in imputed_genes]
    missing_both = [g for g in not_in_regular if g not in imputed_genes]
    in_imputed = [g for g in gene_list if g in imputed_genes]

    # Print summary (fmt is short for format)
    def fmt(glist): return " ".join(sorted(glist)) if glist else "—"

    if in_regular:
        print(f"\n[magenta]Genes present in regular MERFISH data ({len(in_regular)}):[/] {fmt(in_regular)}")
    if in_imputed_only:
        print(f"[cyan]Genes present only in imputed MERFISH data ({len(in_imputed_only)}):[/] {fmt(in_imputed_only)}")
    if in_imputed and in_imputed != in_regular:
        print(f"[green]All genes in imputed dataset ({len(in_imputed)}):[/] {fmt(in_imputed)}")
    if missing_both:
        print(f"\n[red]Genes missing from both regular and imputed datasets ({len(missing_both)}):[/] {fmt(missing_both)}")
    verbose_end_msg()

if __name__ == '__main__':
    main()