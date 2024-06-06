# Guide

## Stitch z-stacks if needed
   * We use [ZEN (blue edition)](https://www.micro-shop.zeiss.com/en/us/softwarefinder/software-categories/zen-blue/) since we have a [Zeiss Lightsheet 7](https://www.zeiss.com/microscopy/en/products/light-microscopes/light-sheet-microscopes/lightsheet-7.html)
   * Open source options: 
      * [TeraStitcher](https://abria.github.io/TeraStitcher/)
      * [ZetaStitched](https://github.com/lens-biophotonics/ZetaStitcher)

## Organize sample folders and raw data
   * Make a folder named after each condition in the experiment folder(s)
      * Make sample?? folders in these and add raw data to them
         * Place a *.czi, *.hf, or one or more folder(s) with tif series into each sample folder
      * Batch processing is easy if you use this convention for naming sample folders: 
         * sample01
         * sample02
         * ...
         * Use a csv, Google sheet, etc. for linking sample IDs to IDs w/ this convention
      * Other patterns for looping can be specified (many scripts have a -p option for that)

## Example experiment folder structure
```bash
.
├── notes.txt
├── env_var.sh
├── sample_key.csv
├── Control
│   ├── sample01
│   └── sample02
├── Treatment
│   ├── sample03
│   └── sample04
├── atlas
│   ├── gubra_ano_25um_bin.nii.gz
│   ├── gubra_ano_combined_25um.nii.gz
│   ├── gubra_ano_split_25um.nii.gz
│   ├── gubra_mask_25um_wo_ventricles_root_fibers_LH.nii.gz
│   ├── gubra_mask_25um_wo_ventricles_root_fibers_RH.nii.gz
│   └── gubra_template_25um.nii.gz
├── reg_results
├── ilastik_brain_mask
│   ├── brain_mask.ilp
│   ├── sample01_slice_0000.tif
│   ├── sample01_slice_0005.tif
│   ├── sample01_slice_0050.tif
│   ├── ...
│   └── sample04_slice_0050.tif
├── vstats
│   └── Control_v_Treatment
├── cluster_validation
│   └── Control_v_Treatment
└── regional_cell_densities
    ├── Control_sample01_regional_cell_densities.csv
    ├── ...
    └── Treatment_sample04_regional_cell_densities.csv
```

## Example sample?? structure
```bash
.
├── atlas_space
├── cfos_seg_ilastik_1
├── clusters
├── parameters
├── reg_inputs
├── regional_cell_densities
├── reg_outputs
└── *.czi
```
         
## Make an exp_notes.txt
   * This helps for keeping track of paths, commands, etc.
   * Most scripts automatically log the command used to run them, appending to .command_log.txt in the current working directory
      * This is a hidden file. Use control+h to view it on Linux. 
```bash
touch exp_notes.txt  # Make the .txt file

cat .command_log.txt  # View command history for the current working directory

cat .command_log.txt | tail -10  # View last 10 lines
```

## Make a sample_key.csv with this organization: 
   * dir_name,condition
   * sample01,control
   * sample02,treatment

## Define environmental variables in a env_var.sh for sourcing
* Environmental variables ($WITH_ALL_CAPS) make it easier to run the commands. 
* For example, $ATLAS can be entered for each command rather than typing or pasting the path/name each time
* They can be set for the duration of terminal session by sourcing (loading) a shell script where they are defined. 
* Copy the example env_var.sh file from /UNRAVEL/_other/env_var_gubra.sh, update paths, etc. and add an alias
* Add: alias exp=". /path/env_var_gubra.sh" to your .bashrc or .zshrc termina config file
```bash
# Run the alias to source the variables before running commands/scripts
exp
```

## Commands/scripts
For help/info on a command/script, run
```
<command> -h

# Or 
<script.py> -h 
```


## Optional: clean tifs
   * If raw data is in the form of a tif series, consider running: 
```bash
clean_tifs -t <dir_name> -v -m -e $DIRS
```

## Typical workflow: 
   * Follow this outline of common commands for analysis steps [Commands](commands.md)


```{todo}
Add support for CCFv3 2020
```

