#!/usr/bin/env python3

"""
Use ``experiment_info.py`` from UNRAVEL to print information about mouse connectivity experiments from the Allen Brain Atlas Mouse Connectivity API.

Notes:
    - https://allensdk.readthedocs.io/en/latest/connectivity.html
    - https://allensdk.readthedocs.io/en/stable/_static/examples/nb/mouse_connectivity.html
    - https://alleninstitute.github.io/AllenSDK/allensdk.api.queries.mouse_connectivity_api.html#allensdk.api.queries.mouse_connectivity_api.MouseConnectivityApi

Usage to find valid region acronyms:
------------------------------------
./experiment_info.py | grep BLA

Usage:
------
    ./experiment_info.py [-r region1 region2 ...]
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

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-r', '--regions', help='Region(s) of interest (e.g., "VISp"). Default: print all regions', nargs='*', action=SM)
    opts.add_argument('-o', '--output', help='Path to output dir for CSVs. Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def find_parent_regions_with_experiments(acronym):
    mcc = MouseConnectivityCache(manifest_file='manifest.json')
    tree = mcc.get_structure_tree()

    # Get region info by acronym
    structures = tree.get_structures_by_acronym([acronym])
    if not structures:
        print(f"No region found for acronym '{acronym}'")
        return

    region_id = structures[0]['id']
    print(f"\nRegion: {acronym} (ID: {region_id})")

    # Get all experiments (cached metadata)
    experiments = mcc.get_experiments(dataframe=True)

    # Check if this region (or descendants) has any experiments
    descendants = tree.descendant_ids([region_id])[0]
    has_experiments = experiments['structure_id'].isin(descendants).any()

    if has_experiments:
        print(f"✅ Experiments found for {acronym} or its descendants.")
        return

    # Otherwise climb up the hierarchy
    ancestors = tree.ancestor_ids([region_id])[0][::-1]  # root→leaf order
    id_to_acr = {n['id']: n['acronym'] for n in tree.nodes()}

    print(f"⚠️ No experiments found for {acronym}. Checking parent regions:")
    for aid in ancestors:
        if aid == region_id:
            continue
        desc = tree.descendant_ids([aid])[0]
        parent_has_exp = experiments['structure_id'].isin(desc).any()
        if parent_has_exp:
            print(f"  → Parent region {id_to_acr.get(aid, aid)} has experiments.")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Initialize MouseConnectivityCache (handles data fetching & caching)
    mcc = MouseConnectivityCache()
    # print(dir(mcc))

    # Grab the allensdk.core.structure_tree.StructureTree object
    structure_tree = mcc.get_structure_tree()

    # Print methods that can be called on structure_tree
    # print(dir(structure_tree))
    # import sys ; sys.exit()

    get_id_acronym_map = structure_tree.get_id_acronym_map()
    regions = list(get_id_acronym_map.keys())

    if args.regions is None:
        print(f"\nAvailable region acronyms:\n {regions}\n")
        import sys ; sys.exit()
    else:
        regions = [r for r in args.regions if r in regions]
        invalid_regions = [r for r in args.regions if r not in regions]
        if invalid_regions:
            print(f"\n[red]Warning: The following region acronyms are invalid and will be ignored: {invalid_regions}[/red]\n")
        if not regions:
            raise ValueError(f"No valid region acronyms found. Valid acronyms are: {list(get_id_acronym_map.keys())}")
    

    # Create list of IDs
    region_ids = [get_id_acronym_map[r] for r in regions if r in get_id_acronym_map]

    experiments = mcc.get_experiments(injection_structure_ids=region_ids)

    # Check if any experiments were found
    if not experiments:
        print(f"\nNo experiments found for regions: {regions}\n")
        for r in args.regions:
            find_parent_regions_with_experiments(r)
        import sys ; sys.exit()

    # Convert experiments to DataFrame for easier viewing
    experiments_df = pd.DataFrame(experiments)
    # Columns: gender, injection_structures, injection_volume, 
    # injection_x, injection_y, injection_z, product_id, specimen_name, 
    # strain, structure_abbrev, structure_id, structure_name, 
    # transgenic_line, transgenic_line_id, id, primary_injection_structure

    # Print the experiments DataFrame with selected columns
    experiments_df = experiments_df[['structure_abbrev', 'structure_id', 'primary_injection_structure', 'transgenic_line', 'injection_volume',  'id', ]]
    experiments_df = experiments_df.sort_values(by='injection_volume', ascending=False).reset_index(drop=True)
    print(f"\nExperiments:\n{experiments_df}\n")

    # Save to CSV
    if args.output is not None:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "experiment_info.csv"
        experiments_df.to_csv(output_path, index=False)
        print(f"Saved experiment info to: {output_path}\n")
    verbose_end_msg()

if __name__ == '__main__':
    main()
