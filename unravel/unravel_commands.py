#!/usr/bin/env python3

"""
Use ``unravel_commands`` or ``uc`` to print a list of commands available in the unravel package. 

Usage to print common commands and descriptions:
------------------------------------------------
    unravel_commands -c -d

Usage to print all commands and module names:
---------------------------------------------
    unravel_commands -m

Usage to print commands matching a specific string:
---------------------------------------------------
    unravel_commands -f <string>

For help on a command, run: 
    <command> -h

Note: 
    - Commands are roughly organized by the order of the workflow and/or the relatedness of the commands.
    - Filtering is case-insensitive and matches substrings in the printed lines (regex).
    - For example, use of -f with -d will find matches in the command name and/or description, presering those lines.

Documentation:
    https://b-heifets.github.io/UNRAVEL/
"""

extended_help = """
If you encounter a situation where a command from the UNRAVEL package has the same name as a command from another package or system command, follow these steps to diagnose and fix the issue:

1. Check the conflicting command:
    - Use the `which` command to determine the location of the executable being called: which <command>
    - This will show the path to the executable that is being invoked when you run the command.

2. Diagnose the conflict:
    - If the path does not point to the UNRAVEL package's command, it means there is a conflict with another package or system command.
    - For example, if you run `which reg` and it points to `/usr/bin/reg` instead of the expected path in your UNRAVEL package's environment, you have identified the conflict.

3. Resolve the conflict:
    - Rename the UNRAVEL command: One way to resolve the conflict is to rename the conflicting command in the `pyproject.toml` file of your UNRAVEL package by adding a unique prefix or suffix.
    - For instance, rename `reg` to `unravel_reg` in the `[project.scripts]` section (i.e., reg = "unravel.register.unravel_reg:main")
    - After making this change, reinstall the package (cd <path/to/clone/of/repo> ; pip install -e .)

4. Re-run the renamed command:
    - Use the new command name to avoid the conflict: unravel_reg -h

5. Create aliases (optional):
    - If you prefer to keep using the original command names, you can create shell aliases in your `.bashrc` or `.zshrc` file to point to the UNRAVEL commands: alias reg="path/to/unravel_env/bin/reg"
    - Reload your shell configuration: source ~/.bashrc  # or source ~/.zshrc

6. Verify the fix:
    - Use the `which` command again to verify that the correct command is being invoked: which unravel_reg  # or which reg if using an alias
"""

import argparse
import re
from rich import print

from unravel.core.argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-c', '--common', help='Only print common commands', action='store_true', default=False)
    parser.add_argument('-m', '--module', help='Print the module (script name and location in the unravel package) for each command', action='store_true', default=False)
    parser.add_argument('-d', '--description', help="Print the description of each command's purpose", action='store_true', default=False)
    parser.add_argument('-f', '--filter', help='Filter commands by a string (e.g, -f reg)', type=str, action=SM)
    parser.add_argument('--extended-help', help='Help on diagnosing and fixing command conflicts', action='store_true', default=False)
    parser.epilog = __doc__
    if parser.parse_known_args()[0].extended_help:
        print(extended_help)
        import sys ; sys.exit()
    return parser.parse_args()


def main():
    args = parse_args()

    commands = {
        "Registration": {
            "reg_prep": {
                "module": "unravel.register.reg_prep",
                "description": "Prepare registration (resample the autofluo image).",
                "common": True
            },
            "reg": {
                "module": "unravel.register.reg",
                "description": "Perform registration (register the autofluo image to an average template).",
                "common": True
            },
            "reg_check": {
                "module": "unravel.register.reg_check",
                "description": "Check registration (aggregate the autofluo and warped atlas images).",
                "common": True
            },
            "reg_check_brain_mask": {
                "module": "unravel.register.reg_check_brain_mask",
                "description": "Check brain mask for over/under segmentation.",
                "common": False
            }
        },
        "Warping": {
            "warp_to_atlas": {
                "module": "unravel.warp.to_atlas",
                "description": "Warp images to atlas space.",
                "common": True
            },
            "warp_to_fixed": {
                "module": "unravel.warp.to_fixed",
                "description": "Warp images to native space.",
                "common": False
            },
            "warp_to_native": {
                "module": "unravel.warp.to_native",
                "description": "Warp images to native space.",
                "common": True
            },
            "warp_points_to_atlas": {
                "module": "unravel.warp.points_to_atlas",
                "description": "Warp cell centroids in tissue space to atlas space.",
                "common": True
            },
            "warp": {
                "module": "unravel.warp.warp",
                "description": "Warp between moving and fixed images.",
                "common": False
            }
        },
        "Segmentation": {
            "seg_copy_tifs": {
                "module": "unravel.segment.copy_tifs",
                "description": "Copy TIF images (copy select tifs to target dir for training ilastik).",
                "common": True
            },
            "seg_brain_mask": {
                "module": "unravel.segment.brain_mask",
                "description": "Create brain mask (segment resampled autofluo tifs).",
                "common": True
            },
            "seg_ilastik": {
                "module": "unravel.segment.ilastik_pixel_classification",
                "description": "Perform pixel classification w/ Ilastik to segment features of interest.",
                "common": True
            },
            "seg_labels_to_masks": {
                "module": "unravel.segment.labels_to_masks",
                "description": "Convert each label to a binary .nii.gz.",
                "common": False
            }
        },
        "Voxel-wise stats": {
            "vstats_apply_mask": {
                "module": "unravel.voxel_stats.apply_mask",
                "description": "Apply mask to image (e.g., nullify artifacts or isolate signals).",
                "common": False
            },
            "vstats_prep": {
                "module": "unravel.voxel_stats.vstats_prep",
                "description": "Prepare immunofluo images for voxel statistics (e.g., background subtract and warp to atlas space).",
                "common": True
            },
            "vstats_z_score": {
                "module": "unravel.voxel_stats.z_score",
                "description": "Z-score images.",
                "common": True
            },
            "vstats_whole_to_avg": {
                "module": "unravel.voxel_stats.whole_to_LR_avg",
                "description": "Average left and right hemispheres together",
                "common": True
            },
            "vstats_hemi_to_avg": {
                "module": "unravel.voxel_stats.hemi_to_LR_avg",
                "description": "If left and right hemispheres were processed separately (less common), average them together.",
                "common": False
            },
            "vstats": {
                "module": "unravel.voxel_stats.vstats",
                "description": "Compute voxel statistics.",
                "common": True
            },
            "vstats_mirror": {
                "module": "unravel.voxel_stats.mirror",
                "description": "Flip and optionally shift content of images in atlas space.",
                "common": False
            }
        },
        "Cluster-wise stats": {
            "cstats_fdr_range": {
                "module": "unravel.cluster_stats.fdr_range",
                "description": "Get FDR q value range yielding clusters.",
                "common": True
            },
            "cstats_fdr": {
                "module": "unravel.cluster_stats.fdr",
                "description": "FDR-correct 1-p value map --> cluster map.",
                "common": True
            },
            "cstats_mirror_indices": {
                "module": "unravel.cluster_stats.recursively_mirror_rev_cluster_indices",
                "description": "Recursively mirror cluster maps for validating clusters in left and right hemispheres.",
                "common": True
            },
            "cstats_validation": {
                "module": "unravel.cluster_stats.validation",
                "description": "Validate clusters w/ cell/label density measurements.",
                "common": True
            },
            "cstats_summary": {
                "module": "unravel.cluster_stats.summary",
                "description": "Summarize info on valid clusters (run after cluster_validation).",
                "common": True
            },
            "cstats_org_data": {
                "module": "unravel.cluster_stats.org_data",
                "description": "Organize CSVs from custer_validation.",
                "common": False
            },
            "cstats_group_data": {
                "module": "unravel.cluster_stats.group_bilateral_data",
                "description": "Group bilateral cluster data.",
                "common": False
            },
            "cstats": {
                "module": "unravel.cluster_stats.cstats",
                "description": "Compute cluster validation statistics.",
                "common": False
            },
            "cstats_index": {
                "module": "unravel.cluster_stats.index",
                "description": "Make a valid cluster map and sunburst plots.",
                "common": False
            },
            "cstats_brain_model": {
                "module": "unravel.cluster_stats.brain_model",
                "description": "Make a 3D brain model from a cluster map (for DSI studio)",
                "common": False
            },
            "cstats_table": {
                "module": "unravel.cluster_stats.table",
                "description": "Create a table of cluster validation data.",
                "common": False
            },
            "cstats_prism": {
                "module": "unravel.cluster_stats.prism",
                "description": "Generate CSVs for bar charts in Prism.",
                "common": False
            },
            "cstats_legend": {
                "module": "unravel.cluster_stats.legend",
                "description": "Make a legend of regions in cluster maps.",
                "common": False
            },
            "cstats_sunburst": {
                "module": "unravel.cluster_stats.sunburst",
                "description": "Create a sunburst plot of regional volumes.",
                "common": False
            },
            "cstats_find_incongruent": {
                "module": "unravel.cluster_stats.find_incongruent_clusters",
                "description": "Find clusters where the effect direction does not match the prediction of cluster_fdr (for validation of non-directional p value maps).",
                "common": False
            },
            "cstats_crop": {
                "module": "unravel.cluster_stats.crop",
                "description": "Crop clusters to a bounding box.",
                "common": False
            },
            "cstats_mean_IF": {
                "module": "unravel.cluster_stats.mean_IF",
                "description": "Compute mean immunofluo intensities for each cluster. ",
                "common": False
            },
            "cstats_mean_IF_summary": {
                "module": "unravel.cluster_stats.mean_IF_summary",
                "description": "Plot mean immunofluo intensities for each cluster.",
                "common": False
            },
            "effect_sizes": {
                "module": "unravel.cluster_stats.effect_sizes.effect_sizes",
                "description": "Calculate effect sizes for clusters.",
                "common": False
            },
            "effect_sizes_sex_abs": {
                "module": "unravel.cluster_stats.effect_sizes.effect_sizes_by_sex__absolute",
                "description": "Calculate absolute effect sizes by sex.",
                "common": False
            },
            "effect_sizes_sex_rel": {
                "module": "unravel.cluster_stats.effect_sizes.effect_sizes_by_sex__relative",
                "description": "Calculate relative effect sizes by sex.",
                "common": False
            }
        },
        "Region-wise stats": {
            "rstats": {
                "module": "unravel.region_stats.rstats",
                "description": "Compute regional cell counts, regional volumes, or regional cell densities.",
                "common": True
            },
            "rstats_summary": {
                "module": "unravel.region_stats.rstats_summary",
                "description": "Summarize regional cell densities.",
                "common": True
            },
            "rstats_mean_IF": {
                "module": "unravel.region_stats.rstats_mean_IF",
                "description": "Compute mean immunofluo intensities for regions.",
                "common": False
            },
            "rstats_mean_IF_in_seg": {
                "module": "unravel.region_stats.rstats_mean_IF_in_segmented_voxels",
                "description": "Compute mean immunofluo intensities in segmented voxels.",
                "common": False
            },
            "rstats_mean_IF_summary": {
                "module": "unravel.region_stats.rstats_mean_IF_summary",
                "description": "Plot mean immunofluo intensities for regions.",
                "common": False
            }
        },
        "Image I/O": {
            "io_metadata": {
                "module": "unravel.image_io.metadata",
                "description": "Handle image metadata.",
                "common": True
            },
            "io_img": {
                "module": "unravel.image_io.io_img",
                "description": "Image I/O operations.",
                "common": False
            },
            "io_nii_info": {
                "module": "unravel.image_io.nii_info",
                "description": "Print info about NIfTI files.",
                "common": True
            },
            "io_nii_hd": {
                "module": "unravel.image_io.nii_hd",
                "description": "Print NIfTI headers.",
                "common": False
            },
            "io_nii": {
                "module": "unravel.image_io.io_nii",
                "description": "NIfTI I/O operations (binarize, convert data type, scale, etc).",
                "common": False
            },
            "io_reorient_nii": {
                "module": "unravel.image_io.reorient_nii",
                "description": "Reorient NIfTI files.",
                "common": False
            },
            "io_nii_to_tifs": {
                "module": "unravel.image_io.nii_to_tifs",
                "description": "Convert NIfTI files to TIFFs.",
                "common": False
            },
            "io_nii_to_zarr": {
                "module": "unravel.image_io.nii_to_zarr",
                "description": "Convert NIfTI files to Zarr.",
                "common": False
            },
            "io_zarr_to_nii": {
                "module": "unravel.image_io.zarr_to_nii",
                "description": "Convert Zarr format to NIfTI.",
                "common": False
            },
            "io_h5_to_tifs": {
                "module": "unravel.image_io.h5_to_tifs",
                "description": "Convert H5 files to TIFFs.",
                "common": False
            },
            "io_tif_to_tifs": {
                "module": "unravel.image_io.tif_to_tifs",
                "description": "Convert TIF to TIFF series.",
                "common": False
            },
            "io_img_to_npy": {
                "module": "unravel.image_io.img_to_npy",
                "description": "Convert images to Numpy arrays.",
                "common": False
            },
            "io_img_to_points": {
                "module": "unravel.image_io.img_to_points",
                "description": "Convert and image into points coordinates.",
                "common": False
            },
            "io_points_to_img": {
                "module": "unravel.image_io.points_to_img",
                "description": "Populate an empty image with point coordinates.",
                "common": False
            }
        },
        "Image tools": {
            "img_avg": {
                "module": "unravel.image_tools.avg",
                "description": "Average NIfTI images.",
                "common": True
            },
            "img_unique": {
                "module": "unravel.image_tools.unique_intensities",
                "description": "Find unique intensities in images.",
                "common": True
            },
            "img_max": {
                "module": "unravel.image_tools.max",
                "description": "Print the max intensity value in an image.",
                "common": True
            },
            "img_bbox": {
                "module": "unravel.image_tools.bbox",
                "description": "Compute bounding box of non-zero voxels in an image.",
                "common": False
            },
            "img_spatial_avg": {
                "module": "unravel.image_tools.spatial_averaging",
                "description": "Perform spatial averaging on images.",
                "common": True
            },
            "img_rb": {
                "module": "unravel.image_tools.rb",
                "description": "Apply rolling ball filter to TIF images.",
                "common": True
            },
            "img_DoG": {
                "module": "unravel.image_tools.DoG",
                "description": "Apply Difference of Gaussian filter to TIF images.",
                "common": False
            },
            "img_pad": {
                "module": "unravel.image_tools.pad",
                "description": "Pad images.",
                "common": False
            },
            "img_resample": {
                "module": "unravel.image_tools.resample",
                "description": "Resample image.nii.gz.",
                "common": False
            },
            "img_resample_points": {
                "module": "unravel.image_tools.resample_points",
                "description": "Resample a set of points [and save as an image].",
                "common": False
            },
            "img_extend": {
                "module": "unravel.image_tools.extend",
                "description": "Extend images (add padding to one side).",
                "common": False
            },
            "img_transpose": {
                "module": "unravel.image_tools.transpose_axes",
                "description": "Transpose image axes.",
                "common": False
            }
        },
        "Atlas tools": {
            "atlas_relabel": {
                "module": "unravel.image_tools.atlas.relable_nii",
                "description": "Relabel atlas IDs.",
                "common": False
            },
            "atlas_wireframe": {
                "module": "unravel.image_tools.atlas.wireframe",
                "description": "Make an atlas wireframe.",
                "common": False
            }
        },
        "Utilities": {
            "utils_agg_files": {
                "module": "unravel.utilities.aggregate_files_from_sample_dirs",
                "description": "Aggregate files from sample directories.",
                "common": True
            },
            "utils_agg_files_rec": {
                "module": "unravel.utilities.aggregate_files_recursively",
                "description": "Recursively aggregate files.",
                "common": False
            },
            "utils_prepend": {
                "module": "unravel.utilities.prepend_conditions",
                "description": "Prepend conditions to files using sample_key.csv.",
                "common": True
            },
            "utils_rename": {
                "module": "unravel.utilities.rename",
                "description": "Rename files.",
                "common": True
            },
            "utils_toggle": {
                "module": "unravel.utilities.toggle_samples",
                "description": "Toggle sample?? folders for select batch processing.",
                "common": False
            },
            "utils_clean_tifs": {
                "module": "unravel.utilities.clean_tif_dirs",
                "description": "Clean TIF directories (no spaces, move non-tifs).",
                "common": False
            },
            "utils_points_compressor": {
                "module": "unravel.utilities.points_compressor",
                "description": "Pack or unpack point data in a CSV file or summarize the number of points per region.",
                "common": False
            }
        }
    }

    print("\n[magenta bold]Category[/], [cyan bold]Command[/], [purple3]Module (-m)[/], [grey50]Description (-d)\n")

    for category, cmds in commands.items():
        if args.common:
            cmds = {k: v for k, v in cmds.items() if v.get("common")}
        if args.filter:
            # Construct the output string for each command
            filtered_cmds = {}
            for cmd, details in cmds.items():
                output = f"{cmd}"
                if args.module:
                    output += f" {details['module']}"
                if args.description:
                    output += f" {details['description']}"
                
                # Perform the filtering on the constructed output string
                if re.search(args.filter, output, re.IGNORECASE):
                    filtered_cmds[cmd] = details
            cmds = filtered_cmds
        if not cmds:
            continue

        print(f"[magenta bold]{category}:")
        for cmd, details in cmds.items():
            output = f"  [cyan bold]{cmd}[/]"
            if args.module:
                output += f" [purple3]{details['module']}[/]"
            if args.description:
                output += f" [grey50]{details['description']}[/]"
            print(output)

if __name__ == "__main__":
    main()
