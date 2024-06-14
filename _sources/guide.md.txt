# Guide

## Help on commands
For help/info on a command, run
```bash
<command> -h
```

## Listing commands
```bash
# List all commands and their descriptions
unravel_commands -d 

# List common commands and their descriptions
unravel_commands -c -d

# List the modules run by each command
unravel_commands -m
```

```{admonition} Info on commands
:class: note dropdown
{py:mod}`unravel.command_list` 

unravel_commands runs ./repo_root_dir/unravel/command_list.py

Commands are defined in the `[project.scripts]` section of the `pyproject.toml` in the root directory of the [UNRAVEL repository](https://github.com/b-heifets/UNRAVEL/blob/dev/pyproject.toml).
```

## Set up

### Back up raw data
   * For Heifets lab members, we keep one copy of raw data on an external drive and another on a remote server (Dan and Austen have access)

### Stitch z-stacks
   * We use [ZEN (blue edition)](https://www.micro-shop.zeiss.com/en/us/softwarefinder/software-categories/zen-blue/) since we have a [Zeiss Lightsheet 7](https://www.zeiss.com/microscopy/en/products/light-microscopes/light-sheet-microscopes/lightsheet-7.html)


:::{admonition} Batch stitching settings
:class: note dropdown
```{figure} _static/batch_stitching_1.JPG
:alt: Batch stitching settings
:height: 500px
:align: center
Select a mid-stack reference slice. Ideally, tissue will be present in each tile of the reference slice. 
```
:::

:::{admonition} Running batch stitching
:class: note dropdown
```{figure} _static/batch_stitching_2.JPG
:alt: Batch stitching settings
:align: center
```
* Drag and drop images to be stitched into this section. 
* For each image in the list, apply the stitching settings one by one (do not go back to a prior image, as settings will no longer stick).
* Select all images (control + A or shift and click)
* Click "Check All"
* Click "Run Selected" 
:::

```{admonition} Open source options for stitching
:class: tip dropdown
* [TeraStitcher](https://abria.github.io/TeraStitcher/)
* [ZetaStitched](https://github.com/lens-biophotonics/ZetaStitcher)
```


### Make sample folders 
   * Make a folder named after each condition in the experiment folder(s)
```
. # This root level folder is referred to as the experiment directory (exp dir) 
├── Control
└── Treatment
```
   * Make sample folders in the directories named after each condition

```{admonition} Name sample folders like sample01, sample02, ...
:class: tip dropdown

This makes batch processing easy.

Use a csv, Google sheet, or whatever else for linking sample IDs to IDs w/ this convention.

Other patterns (e.g., sample???) may be used (commands have a -p option for that).
```

```
.
├── Control
│   ├── sample01
│   └── sample02
└── Treatment
    ├── sample03
    └── sample04
```

### Add images to sample?? dirs

   * For example, image.czi, image.h5, or folder(s) with tif series

```
.
├── Control
│   ├── sample01
│   │   └── <raw/stitched image(s)>
│   └── sample02
│       └── <raw/stitched image(s)>
└── Treatment
    ├── sample03
    │   └── <raw/stitched image(s)>
    └── sample04
        └── <raw/stitched image(s)>
```

```{admonition} Data can be distributed across multiple drives 
:class: tip dropdown

Paths to each experiment directory may be passed into scripts using the -e flag for batch processing

This is useful if there is not enough storage on a single drive. 

Also, spreading data across ~2-4 external drives allows for faster parallel processing (minimizes i/o botlenecks) 

If SSDs are used, distrubuting data may not speed up processing as much. 
```

### Log exp paths, commands, etc.
:::{admonition} Make an exp_notes.txt
:class: tip dropdown
This helps with keeping track of paths, commands, etc..
```bash
cd <path/exp_dir>  # Change the current working directory to an exp dir
touch exp_notes.txt  # Make the .txt file
```
:::

:::{admonition} Automatic logging of scripts
:class: tip dropdown
Most scripts log the command used to run them, appending to ./.command_log.txt.

This is a hidden file. Use control+h to view it on Linux or command+shift+. to view it on MacOS.
```bash
# View command history for the current working directory
cat .command_log.txt  

# View last 10 lines
cat .command_log.txt | tail -10  
```
:::

```{todo}
Log commands instead of scripts
```


### Make a sample_key.csv: 

It should have these columns:
   * dir_name,condition
   * sample01,control
   * sample02,treatment
   * ...

### Define common variables in a shell script
:::{admonition} env_var.sh
:class: note dropdown
* To make commands easier to run, define common variables in a shell script (e.g., env_var.sh)
* Source the script to load variables in each terminal session
* Copy /UNRAVEL/unravel/env_var.sh to an exp dir and update each variable

Add this line to your .bashrc or .zshrc terminal config file: 
```bash
alias exp=". /path/env_var.sh"  # Update the /path/name.sh
```

```bash
# Reopen the terminal or source the updated config file to apply changes
. ~/.zshrc

# Run the alias to source the variables before using them to run commands/scripts
exp
```
:::


### Optional: clean tifs
   * If raw data is in the form of a tif series, consider running: 
```bash
utils_clean_tifs -t <dir_name> -v -m -e $DIRS
```
```{admonition} utils_clean_tifs
:class: tip dropdown
This will remove spaces from files names and move files other than *.tif to the parent directory
```

### Note x/y and z voxel sizes
Extract or specify metadata (outputs to ./sample??/parameters/metadata.txt). Add the resolutions to env_var.sh. 

{py:mod}`unravel.image_io.metadata`

```bash
io_metadata -i <rel_path/full_res_img>  # Glob patterns work for -i
io_metadata -i <tif_dir> -x $XY -z $Z  # Specifying x and z voxel sizes in microns
```
<br>



## Analysis steps

This section provides an overview of common commands available in UNRAVEL, ~organized by their respective steps. 

```{admonition} Common commands
:class: note dropdown
- [Registration](#registration)
    - reg_prep
    - seg_copy_tifs
    - seg_brain_mask
    - reg
    - reg_check
- [Segmentation](#segmentation)
    - seg_copy_tifs
    - seg_ilastik
- [Voxel-wise stats](#voxel-wise-stats)
    - vstats_prep
    - vstats_z_score
    - utils_agg_files
    - vstats_whole_to_avg
    - tools_avg
    - vstats
- [Cluster correction](#cluster-correction)
    - cluster_fdr_range
    - cluster_fdr
    - cluster_mirror_indices
- [Cluster validation](#cluster-validation)
    - cluster_validation
    - cluster_summary
- [Region-wise stats](#region-wise-stats)
    - region_stats
    - region_summary
```

### Registration
#### `reg_prep`
{py:mod}`unravel.register.prep_reg` 
* Prepare autofluo images for registration (resample to a lower resolution)
```bash
reg_prep -i *.czi -x $XY -z $Z -v  # -i options: tif_dir, .h5, .zarr, .tif
```

#### `seg_copy_tifs`
{py:mod}`unravel.segment.copy_tifs`
* Copy resampled autofluo .tif files for segmenting the brain with ilastik
```bash
seg_copy_tifs -i reg_inputs/autofl_??um_tifs -s 0000 0005 0050 -o $(dirname $BRAIN_MASK_ILP) -e $DIRS
```  

#### `seg_brain_mask`
{py:mod}`unravel.segment.brain_mask`
* Makes reg_inputs/autofl_??um_brain_mask.nii.gz and reg_inputs/autofl_??um_masked.nii.gz
```bash
seg_brain_mask -ilp $BRAIN_MASK_ILP -v -e $DIRS
```

#### `reg`
{py:mod}`unravel.register.reg`
* Register an average template brain/atlas to a resampled autofluo brain.

```{admonition} 3 letter orientation code
:class: note dropdown
- Letter options:
    - A/P=Anterior/Posterior
    - L/R=Left/Right
    - S/I=Superior/Interior
- Letter order: 
    - The side of the brain at the positive direction of the x, y, and z axes determines the 3 letters
    - Letter 1: Side of the brain right of z-stack
    - Letter 2: Side of the brain facing bottom of z-stack
    - Letter 3: Side of the brain facing back of z-stack 
```

```bash
reg -m $TEMPLATE -bc -pad -sm 0.4 -ort RPS -a $ATLAS -v -e $DIRS  
```

:::{admonition} If sample orientations vary
:class: tip dropdown
Make a ./sample??/parameters/ort.txt with the 3 letter orientation for each sample and run:
```bash
for d in $DIRS ; do cd $d ; for s in sample?? ; do reg -m $TEMPLATE -bc -pad -sm 0.4 -ort $(cat $s/parameters/ort.txt) -a $ATLAS -v -d $PWD/$s ; done ; done 
```
:::

:::{note}
* We use an adapted version of a `iDISCO/LSFM-specific atlas <https://pubmed.ncbi.nlm.nih.gov/33063286/>`_ 
:::


#### `reg_check`
{py:mod}`unravel.register.check_reg`
* Check registration by copying these images to a target directory: 
    * sample??/reg_outputs/autofl_??um_masked_fixed_reg_input.nii.gz
    * sample??/reg_outputs/atlas_in_tissue_space.nii.gz
```bash
reg_check -e $DIRS -td $BASE/reg_results
```
* View these images with [FSLeyes](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FSLeyes)

:::{admonition} Allen brain atlas coloring
:class: note dropdown
* Replace /home/user/.config/fsleyes/luts/random.lut (location on Linux) with UNRAVEL/_other/fsleyes_luts/random.lut
* Select the atlas and change "3D/4D volume" to "Label image"
:::



### Segmentation

#### `seg_copy_tifs`
{py:mod}`unravel.segment.copy_tifs`
* Copy full res tif files to a target dir for training Ilastik to segment labels of interest 
:::{tip} 
Copy 3 tifs from each sample or 3 tifs from 3 samples / condition
:::
```bash
seg_copy_tifs -i <raw_tif_dir> -s 0100 0500 1000 -o ilastik_segmentation -e $DIRS -v
```

#### `seg_ilastik`
{py:mod}`unravel.segment.ilastik_pixel_classification`
* Perform pixel classification using a trained Ilastik project
```bash
seg_ilastik -i <*.czi, *.h5, or dir w/ tifs> -o seg_dir -ilp $BASE/ilastik_segmentation/trained_ilastik_project.ilp -l 1 -v -e $DIRS 
```


### Voxel-wise stats

#### `vstats_prep`
{py:mod}`unravel.voxel_stats.prep_vstats`
* Preprocess immunofluo images and warp them to atlas space for voxel-wise statistics.
```bash
vstats_prep -i cFos -rb 4 -x $XY -z $Z -o cFos_rb4_atlas_space.nii.gz -v -e $DIRS
```
:::{admonition} Background subtraction
:class: tip dropdown
Removing autofluorescence from immunolabeling improves the sensitivity of voxel-wise comparisons. 

Use -s 3 for 3x3x3 spatial averaging if there is notable noise from voxel to voxel. 

Use a smaller rolling ball radius if you want to preserve punctate signal like c-Fos+ nuclei (e.g., 4)

Use a larger rolling ball radius if you want to preserve more diffuse signal (e.g., 20).

The radius should be similar to the largest feature that you want to preserve. 

You can test parameters for background subtraction with: 
* {py:mod}`unravel.image_tools.spatial_averaging`
* {py:mod}`unravel.image_tools.tif_rb`
    * Copy a tif to a test dir for this. 
    * Use {py:mod}`unravel.image_io.img_io` to create a tif series
:::

#### `vstats_z_score`
{py:mod}`unravel.voxel_stats.z_score`
* Z-score atlas space images using tissue masks (from brain_mask) and/or an atlas mask.

```bash
vstats_z_score -i atlas_space/sample??_cFos_rb4_atlas_space.nii.gz -v -e $DIRS
```
:::{hint}
* atlas_space is a folder in ./sample??/ with outputs from vstats_prep
:::

#### `utils_agg_files`
{py:mod}`unravel.utilities.aggregate_files_from_sample_dirs`
Aggregate pre-processed immunofluorescence (IF) images for voxel-wise stats
```bash
utils_agg_files -i atlas_space/sample??_cFos_rb4_atlas_space_z.nii.gz -e $DIRS -v
```

#### `vstats_whole_to_avg`
{py:mod}`unravel.voxel_stats.whole_to_LR_avg`
* Smooth and average left and right hemispheres together
```bash
# Run this in the folder with the .nii.gz images to process
vstats_whole_to_avg -k 0.1 -tp -v  # A 0.05 mm - 0.1 mm kernel radius is recommended for smoothing
```

:::{seealso} 
{py:mod}`unravel.voxel_stats.hemi_to_LR_avg`
:::

#### `utils_prepend`
{py:mod}`unravel.utilities.prepend_conditions`
* Prepend conditions to filenames based on a CSV w/ this organization
    * dir_name,condition
    * sample01,control
    * sample02,treatment
```bash
utils_prepend -sk $SAMPLE_KEY -f
```


#### `vstats`
{py:mod}`unravel.voxel_stats.vstats`
* Run voxel-wise stats using FSL's randomise_parallel command. 

```bash
vstats -mas mask.nii.gz -v
```

:::{note}
* Outputs in ./stats/
    * vox_p maps are uncorrected 1 - p value maps
    * tstat1: group1 > group2
    * tstat2: group2 > group1
    * fstat*: f contrast w/ ANOVA design (non-directional p value maps)
:::



### Cluster correction
These commands are useful for multiple comparison correction of 1 - p value maps to define clusters of significant voxels. 

#### `tools_avg`
{py:mod}`unravel.image_tools.avg`

* Average *.nii.gz images 
* Visualize absolute and relative differences in intensity
* Use averages from each group to convert non-directioanl 1 - p value maps into directional cluster indices with cluster_fdr
```bash
tools_avg -i Control_*.nii.gz -o Control_avg.nii.gz
```

#### `cluster_fdr_range`
{py:mod}`unravel.cluster_correction.fdr_range`
Outputs a list of FDR q values that yeild clusters.
```bash
# Basic usage
cluster_fdr_range -i vox_p_tstat1.nii.gz -mas mask.nii.gz

# Perform FDR correction on multiple directional 1 - p value maps
for j in *_vox_p_*.nii.gz ; do q_values=$(cluster_fdr_range -mas $MASK -i $j) ; cluster_fdr -mas $MASK -i $j -q $q_values ; done

# Convert a non-directioanl 1 - p value map into a directional cluster index
q_values=$(cluster_fdr_range -i vox_p_fstat1.nii.gz -mas $MASK) ; cluster_fdr -i vox_p_fstat1.nii.gz -mas $MASK -o fstat1 -v -a1 Control_avg.nii.gz -a2 Deep_avg.nii.gz -q $q_values
```

#### `cluster_fdr`
{py:mod}`unravel.cluster_correction.fdr_`
* Perform FDR correction on a 1 - p value map to define clusters
```bash
cluster_fdr -i vox_p_tstat1.nii.gz -mas mask.nii.gz -q 0.05
```

#### `cluster_mirror_indices`
{py:mod}`unravel.cluster_correction.recursive_mirror_index`
* Recursively flip the content of rev_cluster_index.nii.gz images
* Run this in the ./stats/ folder to process all subdirs with reverse cluster maps (cluster IDs go from large to small)
```bash
# Use -m RH if a right hemisphere mask was used (otherwise use -m LH)
cluster_mirror_indices -m RH -v
```


### Cluster validation

#### `cluster_validation`
{py:mod}`unravel.cluster_stats.validate_clusters`
* Warps cluster index from atlas space to tissue space, crops clusters, applies segmentation mask, and quantifies cell/label densities
```bash
# Basic usage:
cluster_validation -e <experiment paths> -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s seg_dir -v

# Processing multiple FDR q value thresholds and both hemispheres:
for q in 0.005 0.01 0.05 0.1 ; do for side in LH RH ; do cluster_validation -e $DIRS -m path/vstats/contrast/stats/contrast_vox_p_tstat1_q${q}/contrast_vox_p_tstat1_q${q}_rev_cluster_index_${side}.nii.gz -s seg_dir/sample??_seg_dir_1.nii.gz -v ; done ; done
```

#### `cluster_summary`
{py:mod}`unravel.cluster_stats.valid_clusters_summary`
* Aggregates and analyzes cluster validation data from validate_clusters
* Update parameters in /UNRAVEL/unravel/cluster_stats/valid_clusters_summary.ini and save it with the experiment
```bash
cluster_summary -c path/valid_clusters_summary.ini -e $DIRS -cvd '*' -vd path/vstats_dir -sk $SAMPLE_KEY --groups group1 group2 -v
```
group1 and group2 must match conditions in the sample_key.csv



### Region-wise stats

#### `rstats`
{py:mod}`unravel.region_stats.regional_cell_densities`
* Perform regional cell counting (label density measurements needs to be added)
```bash
# Use if atlas is already in native space from warp_to_native
rstats -s rel_path/segmentation_image.nii.gz -a rel_path/native_atlas_split.nii.gz -c Saline --dirs sample14 sample36

# Use if native atlas is not available; it is not saved (faster)
rstats -s rel_path/segmentation_image.nii.gz -m path/atlas_split.nii.gz -c Saline --dirs sample14 sample36
```

#### `rstats_summary`
{py:mod}`unravel.region_stats.rstats_summary`
* Plot cell densities for each region and summarize results.
* CSV columns: 
    * Region_ID,Side,Name,Abbr,Saline_sample06,Saline_sample07,...,MDMA_sample01,...,Meth_sample23,...
```bash
rstats_summary --groups Saline MDMA Meth -d 10000 -hemi r
```


### Example sample?? folder structure after analysis
```bash
.
├── atlas_space  # Dir with images warped to atlas space
├── cfos_seg_ilastik_1  # Example dir with segmentations from ilastik
├── clusters  # Dir with cell/label density CSVs from cluster_validation
│   ├── Control_v_Treatment_vox_p_tstat1_q0.005
│   │   └── cell_density_data.csv
│   └── Control_v_Treatment_vox_p_tstat2_q0.05
│       └── cell_density_data.csv
├── parameters  # Optional dir for things like metadata.txt
├── reg_inputs  # From reg_prep (autofl image resampled for reg) and seg_brain_mask (mask, masked autofl)
├── regional_cell_densities  # CSVs with regional cell densities data
├── reg_outputs  # Outputs from reg. These images are typically padded w/ empty voxels. 
└── image.czi # Or other raw/stitched image type
```

### Example experiment folder structure after analysis
```bash
.
├── exp_notes.txt
├── env_var.sh
├── sample_key.csv
├── Control
│   ├── sample01
│   └── sample02
├── Treatment
│   ├── sample03
│   └── sample04
├── atlas
│   ├── gubra_ano_25um_bin.nii.gz  # bin indicates that this has been binarized (background = 0; foreground = 1)
│   ├── gubra_ano_combined_25um.nii.gz  # Each atlas region has a unique intensity/ID
│   ├── gubra_ano_split_25um.nii.gz  # Intensities in the left hemisphere are increased by 20,000
│   ├── gubra_mask_25um_wo_ventricles_root_fibers_LH.nii.gz  # Left hemisphere mask that excludes ventricles, undefined regions (root), and fiber tracts
│   ├── gubra_mask_25um_wo_ventricles_root_fibers_RH.nii.gz
│   └── gubra_template_25um.nii.gz  # Average template brain that is aligned with the atlas
├── reg_results
├── ilastik_brain_mask
│   ├── brain_mask.ilp  # Ilastik project trained with the pixel classification workflow to segment the brain in resampled autofluo images
│   ├── sample01_slice_0000.tif
│   ├── sample01_slice_0005.tif
│   ├── sample01_slice_0050.tif
│   ├── ...
│   └── sample04_slice_0050.tif
├── vstats
│   └── Control_v_Treatment 
│       ├── Control_sample01_rb4_atlas_space_z.tif
│       ├── Control_sample02_rb4_atlas_space_z.tif
│       ├── Treatment_sample03_rb4_atlas_space_z.tif
│       ├── Treatment_sample04_rb4_atlas_space_z.tif
│       └── stats 
│           ├── Control_v_Treatment_vox_p_tstat1.nii.gz  # 1 minus p value map showing where Control (group 1) > Treatment (group2)
│           ├── Control_v_Treatment_vox_p_tstat2.nii.gz  # 1 - p value map showing where Treatment (group 2) > Control (group 1)
│           ├── Control_v_Treatment_vox_p_tstat1_q0.005  # cluster correction folder
│           │   ├── 1-p_value_threshold.txt  # FDR adjusted 1 - p value threshold for the uncorrected 1 - p value map
│           │   ├── p_value_threshold.txt  # FDR adjusted p value threshold
│           │   ├── min_cluster_size_in_voxels.txt  # Often 100 voxels for c-Fos. For sparser signals like amyloid beta plaques, consider 400 or more
│           │   └── ..._rev_cluster_index.nii.gz # cluster map (index) with cluster IDs going from large to small (input for cluster_validation)
│           ├── ...
│           └── Control_v_Treatment_vox_p_tstat2_q0.05
├── cluster_validation
│   ├── Control_v_Treatment_vox_p_tstat1_q0.005
│   │   ├── Control_sample01_cell_density_data.csv
│   │   ├── Control_sample02_cell_density_data.csv
│   │   ├── Treatment_sample03_cell_density_data.csv
│   │   └── Treatment_sample04_cell_density_data.csv
│   ├── ...
│   └── Control_v_Treatment_vox_p_tstat2_q0.05
└── regional_cell_densities
    ├── Control_sample01_regional_cell_densities.csv
    ├── ...
    └── Treatment_sample04_regional_cell_densities.csv
```

```{todo}
Also show the structure of data from cluster_validation and rstats_summary

Add support for CCFv3 2020
```