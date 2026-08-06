#!/usr/bin/env python3

"""
Use ``abca_scRNAseq_filter`` or ``rna_filter`` from UNRAVEL to filter ABCA scRNA-seq cells based on columns and values in the cell metadata.

Notes:
    - region_of_interest_acronym: ACA, AI, AUD, AUD-TEa-PERI-ECT, CB, CTXsp, ENT, HIP, HY, LSX, MB, MO-FRP, MOp, MY, OLF, P, PAL, PL-ILA-ORB, RHP, RSP, sAMY, SS-GU-VISC, SSp, STRd, STRv, TEa-PERI-ECT, TH, VIS, VIS-PTLp
    - mouse columns: cell_label, feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias, neurotransmitter, class, subclass, supertype, cluster, ..., <genes>
    - human columns: cell_label, feature_matrix_label, region_of_interest_acronym, x, y, cluster_alias, neurotransmitter, supercluster, cluster, subcluster, ..., <genes>
    - For multiple columns and values, the number of columns must match the number of values.

Next steps:
    - ``abca_sunburst_expression``

Usage:
------
    abca_scRNAseq_filter -i path/expression.csv [-c column1 column2 ... -val value1 value2 ...] [-s mouse | human] [-ct Neurons | Nonneurons] [-split split_column] [-o output] [-v]
"""

import re

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.allen_institute.abca.merfish.merfish_filter import filter_dataframe
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the scRNAseq CSV file', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-split', '--split-column', dest='split_column', help='Write one CSV per unique value in this column. In this mode, -o specifies an output directory.', default=None, action=SM)
    opts.add_argument('-c', '--columns', help='Columns to filter by (e.g., region_of_interest_acronym)', nargs='*', action=SM)
    opts.add_argument('-val', '--values', help='Values used for filtering. For multiple columns and values, the number of columns must match the number of values.', nargs='*', action=SM)
    opts.add_argument('-s', '--species', help='Species to use (human or mouse). Default: mouse', default='mouse', action=SM)
    opts.add_argument('-o', '--output', help='Output path for the filtered cell metadata', default=None, action=SM)
    opts.add_argument('-ct', '--cell_type', help='Cell type to use (neurons or nonneurons). Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def filter_by_cell_type(cell_df: pd.DataFrame, species: str, cell_type: str | None) -> pd.DataFrame:
    """Filter cells by species and cell type (neurons vs nonneurons)."""
    if not cell_type:
        return cell_df
    ct = cell_type.lower()

    if species == 'mouse' and 'class' in cell_df.columns:
        is_neuron = cell_df['class'].str.split().str[0].astype(int) <= 29
        return cell_df[is_neuron] if ct == 'neurons' else cell_df[~is_neuron]

    elif species == 'human' and 'supercluster' in cell_df.columns:
        nonneurons = {'Oligodendrocyte', 'Committed oligodendrocyte precursor', 'Oligodendrocyte precursor',
                      'Astrocyte', 'Ependymal', 'Microglia', 'Vascular', 'Bergmann glia', 'Fibroblast', 'Choroid plexus'}
        is_nonneuronal = cell_df['supercluster'].isin(nonneurons)
        return cell_df[~is_nonneuronal] if ct == 'neurons' else cell_df[is_nonneuronal]

    print(f"[yellow]Warning: Missing expected metadata columns for {species}, returning unfiltered data.[/yellow]")
    return cell_df

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if bool(args.columns) != bool(args.values):
        raise ValueError("--columns and --values must be provided together.")

    if args.columns and len(args.columns) != len(args.values):
        raise ValueError(
            f"The # of columns ({len(args.columns)}) must match "
            f"the # of values ({len(args.values)})."
        )

    if not args.columns and not args.split_column:
        raise ValueError(
            "Provide --columns and --values for normal filtering, "
            "or --split-column to write one file per unique value."
        )

    # Load the cell metadata
    cell_df = pd.read_csv(args.input, dtype={'cell_label': str})

    print(f"\n    Initial cell metadata shape:\n    {cell_df.shape}")

    if args.verbose:
        print("\nFirst five rows:")
        print(cell_df.head())

    # Filter by cell type if specified
    cell_df = filter_by_cell_type(cell_df, species=args.species, cell_type=args.cell_type)

    # Optional filters applied before splitting
    if args.columns:
        filtered_df = filter_dataframe(
            cell_df,
            args.columns,
            args.values
        )
    else:
        filtered_df = cell_df

    print("\nFiltered cell metadata shape:", filtered_df.shape)

    # Write one CSV per unique value in the split column
    if args.split_column:
        if args.split_column not in filtered_df.columns:
            raise ValueError(
                f"Column not found: {args.split_column}"
            )

        input_stem = Path(args.input).stem

        if args.output is not None:
            output_dir = Path(args.output)
        else:
            output_dir = Path(
                f"{input_stem}__by_{args.split_column}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        n_outputs = 0

        for value, group_df in filtered_df.groupby(
            args.split_column,
            sort=False,
            dropna=False
        ):
            value_label = "NA" if pd.isna(value) else str(value)

            # Human A29-A30 -> Human_A29-A30
            safe_value = re.sub(
                r'[^A-Za-z0-9._-]+',
                '_',
                value_label
            ).strip('_')

            output_path = output_dir / (
                f"{input_stem}__{safe_value}.csv"
            )

            group_df.to_csv(output_path, index=False)

            print(
                f"Saved {group_df.shape[0]:,} cells: "
                f"{output_path}"
            )

            n_outputs += 1

        print(
            f"\nSaved {n_outputs} files to: "
            f"{output_dir}"
        )

        verbose_end_msg()
        return

    # Original single-output behavior
    if args.verbose and not filtered_df.empty:
        print("\nFirst filtered row:")
        print(filtered_df.iloc[0])

    for column in args.columns:
        print(f"\nUnique values for {column}:")
        print(filtered_df[column].unique())

    if args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = Path(
            f"{Path(args.input).stem}_filtered.csv"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered_df.to_csv(output_path, index=False)

    print(f"\nFiltered data saved to: {output_path}")

    verbose_end_msg()


if __name__ == '__main__':
    main()
