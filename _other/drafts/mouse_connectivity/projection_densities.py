#!/usr/bin/env python3

"""
Use ``projection_densities.py`` from UNRAVEL to analyze connectivity data from the Allen Brain Atlas Mouse Connectivity API.

Notes:
    - https://allensdk.readthedocs.io/en/latest/connectivity.html
    - https://allensdk.readthedocs.io/en/stable/_static/examples/nb/mouse_connectivity.html
    - https://alleninstitute.github.io/AllenSDK/allensdk.api.queries.mouse_connectivity_api.html#allensdk.api.queries.mouse_connectivity_api.MouseConnectivityApi

"""

import pandas as pd
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-s', '--source', help='Source structure acronym(s)', required=True, nargs='*', action=SM)
    reqs.add_argument('-t', '--target', help='Target structure acronym(s)', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-e', '--exp_type', help='Experiment type (e.g., cre, wt, all). Default: all', default='all', action=SM)
    opts.add_argument('-d', '--descendants', help='Include descendants of target structures. Default: False', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Path to output dir for CSVs. Default: projection_densities', default='_projection_densities', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Initialize MouseConnectivityCache (handles data fetching & caching)
    mcc = MouseConnectivityCache(manifest_file='manifest.json')

    # grab the StructureTree instance
    structure_tree = mcc.get_structure_tree()

    # Find structure IDs for source & target structures
    source_structures = [structure_tree.get_structures_by_acronym([s])[0] for s in args.source]
    target_structures = [structure_tree.get_structures_by_acronym([t])[0] for t in args.target]
    target_structure_ids = [t['id'] for t in target_structures]

    # Fetch experiment data for each source structure
    experiment_ids = []
    for structure in source_structures:
        if args.exp_type == 'all':
            experiments = mcc.get_experiments(injection_structure_ids=[structure['id']])
        elif args.exp_type == 'cre':
            experiments = mcc.get_experiments(cre=True, injection_structure_ids=[structure['id']])
        elif args.exp_type == 'wt':
            experiments = mcc.get_experiments(cre=False, injection_structure_ids=[structure['id']])
        else:
            raise ValueError(f'Invalid experiment type: {args.exp_type}')

        experiment_ids.extend([exp['id'] for exp in experiments])

    print(f'\n{len(experiment_ids)} experiments found for source regions: [green]{args.source}\n')

    # Get the projection data for the target structure
    structure_unionizes = mcc.get_structure_unionizes(
        experiment_ids=experiment_ids, # List of experiment IDs.  Corresponds to section_data_set_id in the API.
        structure_ids=target_structure_ids,  # Filter with list of target structure IDs
        is_injection=False,  # Ensure projection data is retrieved, not injection site
        include_descendants=args.descendants  # Include any subregions of ACB
    )

    # Sort by experiment ID and then hemisphere
    structure_unionizes = structure_unionizes.sort_values(by=['experiment_id', 'hemisphere_id'])  # Hemi 1 = left, 2 = right, 3 = both

    # Columns: experiment_id, hemisphere_id, id, is_injection, 
    # max_voxel_density, max_voxel_x, max_voxel_y, max_voxel_z, 
    # normalized_projection_volume, projection_density, 
    # projection_energy, projection_intensity, projection_volume, 
    # structure_id, sum_pixel_intensity, sum_pixels, 
    # sum_projection_pixel_intensity, sum_projection_pixels, volume

    # Join the transgenic_line column
    all_experiments = mcc.get_experiments(dataframe=True)
    tg_lines = [all_experiments.loc[experiment_id] for experiment_id in structure_unionizes['experiment_id']]

    # Get the transgenic line for each experiment
    structure_unionizes['transgenic_line'] = [tg_line['transgenic_line'] for tg_line in tg_lines]

    # Make a promoter column (first word of transgenic_line separated by dashes)
    structure_unionizes['promoter'] = [
        line.split('-')[0] if isinstance(line, str) else 'NA' 
        for line in structure_unionizes['transgenic_line']
    ]

    
    # Save the full results to a CSV file
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path('_projection_densities')
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = Path(f'projection_densities_{args.source}_to_{args.target}_exp_{args.exp_type}.csv')
    output_path = output_dir / summary_csv
    structure_unionizes.to_csv(output_path, index=False)

    # Keep key columns for further analysis of projections in the target structure(s)
    # projection_energy = projection density × projection intensity
    # projection_intensity = sum_pixel_intensity / sum_pixels  # In segmented pixels
    projection_df = structure_unionizes[['promoter', 'experiment_id', 'hemisphere_id', 'projection_volume', 'volume', 'projection_density', 'projection_intensity', 'projection_energy']].copy()

    # Display the results
    pd.set_option('display.float_format', '{:.6f}'.format)
    
    # Ensure proper modification without chaining
    projection_df.loc[:, 'injection_volume'] = projection_df['experiment_id'].map(
        lambda exp_id: all_experiments.loc[exp_id, 'injection_volume']
    )

    # Format injection_volume correctly (3 decimal places, no trailing zeros)
    projection_df.loc[:, 'injection_volume'] = projection_df['injection_volume'].apply(lambda x: f"{x:.3f}".rstrip('0').rstrip('.'))

    # Reset the index
    projection_df.reset_index(drop=True, inplace=True)

    
    # Make a df for the right hemisphere (hemisphere_id = 2; ipsilateral to injection site)
    right_hemi_df = projection_df[projection_df['hemisphere_id'] == 2]
    right_hemi_df = right_hemi_df.drop(columns='hemisphere_id')
    right_hemi_df = right_hemi_df.sort_values(by='projection_density', ascending=False)
    right_hemi_df = right_hemi_df.reset_index(drop=True)
    print(f'\nIpsilateral to injection site:\n{right_hemi_df}\n')

    # Make a df for the left hemisphere (hemisphere_id = 1; contralateral to injection site)
    left_hemi_df = projection_df[projection_df['hemisphere_id'] == 1]
    left_hemi_df = left_hemi_df.drop(columns='hemisphere_id')
    left_hemi_df = left_hemi_df.sort_values(by='projection_density', ascending=False)
    left_hemi_df = left_hemi_df.reset_index(drop=True)
    print(f'\nContralateral to injection site:\n{left_hemi_df}\n')

    # Save the results
    right_hemi_csv = Path(str(summary_csv).replace('.csv', '_RH.csv'))
    left_hemi_csv = Path(str(summary_csv).replace('.csv', '_LH.csv'))
    right_output_path = output_dir / right_hemi_csv
    left_output_path = output_dir / left_hemi_csv
    right_hemi_df.to_csv(right_output_path, index=False)
    left_hemi_df.to_csv(left_output_path, index=False)

    verbose_end_msg()

if __name__ == '__main__':
    main()
