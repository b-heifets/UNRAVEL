#!/usr/bin/env python3

"""
Use Allen_RNAseq_expression_in_mice.py from UNRAVEL to analyze scRNA-seq expression in neurons, astrocytes, and microglia,
providing statistics for each major brain region and the whole brain.
"""

from pathlib import Path
import anndata
import pandas as pd
from rich import print
from rich.traceback import install
import merfish as m

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the data', required=True, action=SM)
    reqs.add_argument('-g', '--genes', help='Space-separated list of genes to analyze', required=True, nargs='*', action=SM)
    reqs.add_argument('-o', '--output', help='path/expression_metrics.csv', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()

def load_RNAseq_mouse_cell_metadata(download_base):
    cell_metadata_path = download_base / "metadata/WMB-10X/20231215/cell_metadata.csv"
    cell_df = pd.read_csv(cell_metadata_path, dtype={'cell_label': str},
                          usecols=['cell_label', 'library_label', 'feature_matrix_label', 'dataset_label', 
                                   'x', 'y', 'cluster_alias', 'region_of_interest_acronym'])
    cell_df.set_index('cell_label', inplace=True)
    return cell_df

def load_mouse_RNAseq_gene_metadata(download_base):
    gene_metadata_path = download_base / "metadata/WMB-10X/20231215/gene.csv"
    gene_df = pd.read_csv(gene_metadata_path)
    gene_df.set_index('gene_identifier', inplace=True)
    return gene_df

def classify_cells(cell_df):
    # Define cell type classifications
    neuronal_classes = [str(i).zfill(2) for i in range(1, 30)]  # Classes 01-29 are neuronal
    astrocyte_subclasses = ["317", "318", "319", "320"]  # Subclasses for astrocytes
    microglia_subclass = ["334"]  # Subclass for microglia

    cell_df['cell_type'] = 'Other'
    cell_df.loc[cell_df['class'].astype(str).isin(neuronal_classes), 'cell_type'] = 'Neuron'
    cell_df.loc[cell_df['subclass'].astype(str).isin(astrocyte_subclasses), 'cell_type'] = 'Astrocyte'
    cell_df.loc[cell_df['subclass'].astype(str).isin(microglia_subclass), 'cell_type'] = 'Microglia'

    return cell_df

def calculate_expression_metrics(gdata, cell_df, genes):
    # Prepare DataFrame to store results
    results = []

    # Include 'Whole Brain' as a region
    cell_df['region'] = cell_df['region_of_interest_acronym']
    cell_df['region'].fillna('Whole Brain', inplace=True)
    regions = cell_df['region'].unique()

    # Get unique combinations of cell_type and region
    group_combinations = cell_df[['cell_type', 'region']].drop_duplicates()

    for gene in genes:
        for _, row in group_combinations.iterrows():
            cell_type = row['cell_type']
            region = row['region']
            # Filter cells by cell type and region
            cells_of_interest = cell_df[(cell_df['cell_type'] == cell_type) & (cell_df['region'] == region)]
            cell_indices = cells_of_interest.index.intersection(gdata.index)
            gene_expression = gdata.loc[cell_indices, gene]

            # Calculate metrics
            expressing_cells = gene_expression[gene_expression > 0].count()
            total_cells = gene_expression.count()
            mean_expression = gene_expression.mean()
            percent_expressing = (expressing_cells / total_cells * 100) if total_cells > 0 else 0

            # Store the results
            results.append({
                'gene': gene,
                'cell_type': cell_type,
                'region': region,
                'mean_expression': mean_expression,
                'percent_expressing': percent_expressing,
                'expressing_cells': expressing_cells,
                'total_cells': total_cells
            })

    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    return results_df

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Load and classify cell metadata
    cell_df = load_RNAseq_mouse_cell_metadata(download_base)
    cell_df = m.join_cluster_details(cell_df, download_base)  # Adds 'class', 'subclass'
    cell_df = classify_cells(cell_df)

    # Load gene metadata and filter for selected genes
    gene_df = load_mouse_RNAseq_gene_metadata(download_base)
    gene_filtered = gene_df[gene_df['gene_symbol'].isin(args.genes)]

    # Load expression data from each file and concatenate
    expression_matrices_dir = download_base / 'expression_matrices'
    exp_dfs = []
    for file in expression_matrices_dir.rglob('WMB-10X*/**/*-log2.h5ad'):
        matrix_prefix = file.stem.replace('-log2', '')
        cell_filtered = cell_df[cell_df['feature_matrix_label'] == matrix_prefix]
        if not cell_filtered.empty:
            ad = anndata.read_h5ad(file, backed='r')
            exp_df = ad[cell_filtered.index, gene_filtered.index].to_df()
            exp_df.columns = gene_filtered['gene_symbol']
            exp_dfs.append(exp_df)
            ad.file.close()

    # Concatenate all gene expression data
    gdata = pd.concat(exp_dfs, axis=0)

    # Calculate expression metrics for each gene, cell type, and region
    results_df = calculate_expression_metrics(gdata, cell_df, args.genes)

    # Display the results
    print("\nExpression metrics by cell type and region:\n")
    print(results_df)

    # Save the results to a CSV file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(, index=False)

    verbose_end_msg()

if __name__ == '__main__':
    main()
