# Guide

* If you are unfamiliar with the terminal, start here: 
   * [Linux in 100 seconds](https://www.youtube.com/watch?v=rrB13utjYV4)
   * [Bash in 100 seconds](https://www.youtube.com/watch?v=I4EWvMFj37g)
   * [Interactive Linux Survival guide](https://linuxsurvival.com/)
   * Refer to common commands and tips in the cheat sheet (click to expand dropdown):

:::{admonition} Terminal command cheat sheet
:class: hint dropdown

### Working Directory

The working directory, or current directory, is the folder in the file system that a user or program is currently accessing. 

- **Default Location**: The terminal typically starts in your home directory.
- **Relative Paths**: Commands use paths relative to the working directory.
- **Changing Directories**: Use `cd /path/to/directory` to change the working directory.
- **Viewing the Directory**: Use `pwd` to display the current working directory.
- **Importance**: Knowing your working directory is often crucial for executing commands and managing files as intended.

### Stopping a command
- `Ctrl + C`: Interrupt the command

### Learning About Commands
- **Help Option**: Many commands offer a `--help` option to provide a quick overview of usage. For example, `ls --help` or `ls -h`.
- **Manual Pages**: Use `man <command>` to access the manual page for detailed information about a command. For example, `man ls` provides options and descriptions for the `ls` command.
- **`which`**: Use `which <command>` to locate the executable file for a command. For example, `which python` shows where the Python interpreter is installed.

### Listing Files
- `ls`: List files and directories.
- `ls -l`: List files in long format, including details like permissions, size, and modification date.
- `ls -a`: List all files, including hidden files, which start with a "." (unravel commands are logged in a hidden file [.command_log.txt]). 
- `ls -1`: List files in a single column.

### Viewing and Creating Files
- `cat <filename>`: Display the contents of a file.
- `echo "string" > new.txt`: Create a new file named `new.txt` and write "string" to it.
- `echo "string" >> new.txt`: Append "string" to the existing `new.txt` file.
- `touch new.txt`: Create a new file that is empty

### File/Folder Management
- `mkdir <dir_name>`: Make directory
- `rm -rf <dir_name>`: Delete folder and all contents recursively (be careful where you run this and what patterns you use)
- `rm <file>` or `rm <path/file>`

### Navigation and Shortcuts
- **Tab completion**: Use tab to auto-complete file and directory names.
- **Up arrow**: Scroll through command history. In zsh, type a partial command and press the up arrow to find past commands starting with the typed string.
- `cd <path>`: Change the current directory to `<path>`. Drag/drop a file or folder into the terminal to paste the path to it. Or select the file/folder, hit Ctrl + C, select the terminal, and press Ctrl + Shift + V.
- `cd <Tab>` or `cd <Tab Tab>`: To see folders in the working dir that you can cd to (with zsh use Tab and Shift + Tab to cycle --> enter or space)
- `cd ..`: Move up one directory level.
- `cd ../..`: Move up two directory levels.
- `cd ../dir`: Move up one directory and then into `dir`.
- `cd -`: Switch to the previous directory.
- `cd`: Change to the home directory.
- `cd ~/`: Change to the home directory using the tilde shortcut.

### Command History
- `history`: Print the history of terminal commands
- `!3`: Run the third command in the history
- `cat .command_log.txt`: Print the history of unravel commands
- `cat .command_log.txt | tail -10`: Print the last 10 lines
- `cat .command_log.txt | head -10`: Print the first 10 lines

### Keyboard Shortcuts
- **Copy/Paste**: 
  - `Ctrl + Shift + C`: Copy text
  - `Ctrl + Shift + V`: Paste text.
  - Or select text and click the middle wheel on the mouse to copy and paste.

- **Movement**: 
  - `Ctrl + A`: Move to the beginning of the line.
  - `Ctrl + E`: Move to the end of the line.
  - `Ctrl + Arrow`: Move word by word.

- **Deleting**: 
  - `Ctrl + W`: Delete the word before the cursor (space-separated for bash, additional delimiters for zsh).
  - `Ctrl + U`: Delete from the cursor to the beginning of the line.
  - `Ctrl + K`: Delete from the cursor to the end of the line.
  - `Ctrl + Y`: Paste the last killed text.

- **Find**: 
  - `Ctrl + Shift + F`: Open the search bar to find text.

### Command Execution and Scripting
- Using `;` vs. `&`: `;` chains commands to execute sequentially, while `&` runs a command in the background.
- Another way to chain commands is to "pipe" ("|" character) the output from one command (what would be printed to the terminal) so it is used as the input of the next command
   - For example, `cat <filename> | wc -l`: Cat would print the contents of <filename>, but here this is used as the input for wc, which counts the number of lines (e.g., rows in a csv)
- Parentheses `()` for multi-line commands: Group commands to execute them in a subshell.

### Global Variables
- `$PWD`: Variable with the current working directory path.
- `$PATH`: List of directories that have executable files. Allows for executing scripts without providing the full path (e.g., path/script.py --> script.py). Folders with UNRAVEL scripts don't need to be added to the $PATH if it installed w/ `pip`. 
- See this **[guide](https://b-heifets.github.io/UNRAVEL/guide.html#defining-common-variables-for-command-arguments)** to define common command arguments as global variables in env_var.sh (so they can be loaded in each terminal session)

### Batch Processing Via Loops
- For loops examples: 
   - `for d in dir* ; do original_dir=$PWD ; cd $d ; pwd ; cd $original_dir ; done` 
   - `for s in sample?? ; do cat $s/parameters/metadata.txt ; done`
   - `for d in <space separated list of experiment folder> ; do cd $d ; for s in sample?? ; do echo $s ; done ; done`
   - `for i in 1 2 3 4; do echo $i ; done`
   - `for i in {1..10}; do echo $i ; done`
   - Parallel processing w/ &: `for i in *.nii.gz ; do fslmaths $i -bin ${i::-7}_bin -odt char & done  # Binarizes all images, output data type 8-bit, ${i::-7} trims last 7 characters in bash (does not work in zsh)` (run `echo` to see when processes are done).

### Variables and Substitution
- `$PWD`: Variable with the current working directory path.
- `$()`: Command substitution to capture output for use in commands (e.g., `x=$(for )`)

### File Searching and Manipulation
- `find`: Search for files in a directory hierarchy.
  - `find . -name "*.txt"`: Search for text files matching this pattern.
  - `find $PWD -name "*.txt" -exec rm {} \;`: Find all `.txt` files and delete them.
- `grep`: Search text using patterns.
  - `grep -r <string_in_files>`: Recursively search for a pattern
  - `grep -r --exclude-dir=docs <pattern>`: Search for a pattern while excluding specific directories.
  - `grep -r <pattern1> | grep <pattern2>`: Search for a pattern filter to preserve lines with a second string
  - `grep -r <pattern1> | grep -v <pattern2>`: Search for a pattern filter to exlude lines with a second string
- [`fzf`](https://github.com/junegunn/fzf): A command-line fuzzy finder that allows you to search and filter items interactively, providing a fast and efficient way to locate files, commands, or history entries.

### Text Processing
- `sed`: Stream editor for filtering and transforming text.
  - `sed 's/old/new/g' file`: Replace all occurrences of `old` with `new` in `file` (use *.txt for multiple files)

### Aliases

Aliases are shortcuts for longer commands or sequences of commands, making it easier and quicker to execute frequently used commands. You can create aliases in your shell configuration file (like `.bashrc` for Bash or `.zshrc` for Zsh).

  #### How to Create Aliases:
  - Open your shell configuration file (.bashrc or .zshrc) with **[VS Code](https://code.visualstudio.com/download)** or **[nano](https://www.youtube.com/watch?v=DLeATFgGM-A)**
    ```bash
    # For example:
    nano ~/.bashrc  # For Bash users
    ```
  - Add alias definitions in the format:
    ```bash
    alias shortname='full command'
    ```
    For example:
    ```bash
    alias ll='ls -l'
    alias ilastik='path/to/ilastik_executable'  # For launching Ilastik via the terminal by running: ilastik
    alias i="io_nii_info -i "
    alias gs='git status'
    ```
  - Save the file and reload your configuration:
    ```bash
    source ~/.bashrc  # For Bash users
    ```

### FSL Commands for NIfTI files (.nii.gz extension)
- `fslmaths`: Perform mathematical operations on images.
  - `add`
  - `sub`,
  - `bin` (binarize)
  - `uthr` (Zero out intenisties above upper threshold)
  - `thr` (Zero out intenisties below  threshold)
  - `mas` (mask).
  - Use `-odt` at end to set output data type (char for 8-bit and short for unsigned 16-bit). Default is float 32-bit. Pay attention to the max range that each data type can represent (e.g., 255 for 8-bit and 65,535 for 16-bit).
  - ".nii.gz" is automatically added
  - Examples:
  - `fslmaths img_1 -bin img_1_bin -odt char  # char is for 8-bit`
  - `fslmaths img_2 -mas img_1_bin -odt short  # This used img_1_bin as a mask`
  - `fslmaths img_1_bin -mul -1 -add 1 img_1_bin_inv -odt char  # This inverts a mask`
  - `fslmaths img_1 -sub img_2 diff  # Then check if the images are the same: fslstats diff -R `
  - `fslmaths img_1 -sub img_1 blank  # Make an empty image for adding masks of each region`
  - `for i in 1 56 672 ; do fslmaths atlas -thr $i -uthr $i region_${i} -odt short`
  - `for i in region_mask*.nii.gz ; do fslmaths blank -add $i blank ; done ; mv blank.nii.gz all_regions.nii.gz`
- `fslstats`: Compute statistics on images (-R, -V, -M)
- `fslroi`: Crop or expand images. 
- `fslcpgeom`: Copy header info (e.g., resolution and position in global space for viewing) from one image to another.

### Killing a Process
If `Ctrl + C` doesn't stop the command, you can kill the process:

- **Find the Process ID (PID)**:
  - Use `ps aux | grep <process_name>` to find the PID of the process. Replace `<process_name>` with the name of the command or process you want to stop.
  - Alternatively, use `pgrep <process_name>` to directly get the PID.

- **Kill the Process**:
  - Use `kill <PID>` to send a termination signal to the process. Replace `<PID>` with the actual process ID.
  - If the process doesn’t stop, force it with `kill -9 <PID>`.
:::

---

## Help on commands
* For help/info on a command, run this in the terminal:
```bash
<command> -h
```
* Help guides often include info on prereqs, inputs, outputs, next steps, usage, and other notes.
* Viewing the help in the terminal is helpful to see default values for arguments not mentioned in this guide.
* Some commands have additional options that are not covered in this guide
* Provide -v when running commands for verbose mode (to see info about function calls, parameters, etc.)

:::{admonition} Syntax related to commands
:class: hint dropdown
* The symbols < and > indicate placeholders. Replace \<command\> with the actual command name you want to learn more about.
* Square brackets [ ] in command syntax signify optional elements. 
* Double backticks are used in help guides to indicate a command. (e.g., \`\`command\`\`)
* Asterisks act as wildcards for matching patterns in strings
* ?? means two digits
:::

To view help on arguments for each command in the online documentation, go to the page for that module/script, scroll to the parse_args() function, and click the link for viewing the source code.

---

## Listing commands
```bash
# List common commands
unravel_commands -c

# List common commands and filter results
uc -f vstats  # Just print commands related to voxel-wise statistics

# List common commands and their descriptions
uc -c -d

# List all commands and the modules that they run
uc -m
```

:::{hint}
* **Prefixes** group together related commands. Use **tab completion** in the terminal to quickly view and access sets of commands within each group.
:::

---

## Common commands

::::{tab-set}

::: {tab-item} Registration
- [**reg_prep**](unravel.register.reg_prep): Prepare registration (resample the autofluo image to lower res).
- [**reg**](unravel.register.reg): Perform registration (e.g., register the autofluo image to an average template).
- [**reg_check**](unravel.register.reg_check): Check registration (aggregate the autofluo and warped atlas images).
:::

::: {tab-item} Warping
- [**warp_to_atlas**](unravel.warp.to_atlas): Warp full res tissue space images to atlas space.
- [**warp_to_native**](unravel.warp.to_native): Warp images to native img space, unpad, and scale to full res.
- [**warp_to_fixed**](unravel.warp.to_fixed): Warp full res tissue space images to fixed img space and unpad.
:::

::: {tab-item} Segmentation
- [**seg_copy_tifs**](unravel.segment.copy_tifs): Copy TIF images (copy select tifs to target dir for training ilastik).
- [**seg_brain_mask**](unravel.segment.brain_mask): Create brain mask (segment resampled autofluo tifs).
- [**seg_ilastik**](unravel.segment.ilastik_pixel_classification): Perform pixel classification w/ Ilastik to segment features of interest.
:::

::: {tab-item} Voxel-wise stats
- [**vstats_prep**](unravel.voxel_stats.vstats_prep): Prepare immunofluo images for voxel statistics (e.g., background subtract and warp to atlas space).
- [**vstats_z_score**](unravel.voxel_stats.z_score): Z-score images.
- [**vstats_whole_to_avg**](unravel.voxel_stats.whole_to_LR_avg): Average left and right hemispheres together.
- [**vstats**](unravel.voxel_stats.vstats): Compute voxel statistics.
:::

::: {tab-item} Cluster-wise stats
- [**cstats_fdr_range**](unravel.cluster_stats.fdr_range): Get FDR q value range yielding clusters.
- [**cstats_fdr**](unravel.cluster_stats.fdr): FDR-correct 1-p value map → cluster map.
- [**cstats_mirror_indices**](unravel.cluster_stats.recursively_mirror_rev_cluster_indices): Recursively mirror cluster maps for validating clusters in left and right hemispheres.
- [**cstats_validation**](unravel.cluster_stats.validation): Validate clusters w/ cell/label density measurements.
- [**cstats_summary**](unravel.cluster_stats.summary): Summarize info on valid clusters (run after cluster_validation).
:::

::: {tab-item} Region-wise stats
- [**rstats**](unravel.region_stats.rstats): Compute regional cell counts, regional volumes, or regional cell densities.
- [**rstats_summary**](unravel.region_stats.rstats_summary): Summarize regional cell densities.
:::

::: {tab-item} Image I/O
- [**io_metadata**](unravel.image_io.metadata): Save raw voxel dimensions in microns and image dimensions to parameters/metadata.txt. 
- [**io_nii_info**](unravel.image_io.nii_info): Print info about NIfTI files.
:::

::: {tab-item} Image tools
- [**img_avg**](unravel.image_tools.avg): Average NIfTI images.
- [**img_unique**](unravel.image_tools.unique_intensities): Find unique intensities in images.
- [**img_max**](unravel.image_tools.max): Print the max intensity value in an image.
- [**img_spatial_avg**](unravel.image_tools.spatial_averaging): Perform spatial averaging on images.
- [**img_rb**](unravel.image_tools.rb): Apply rolling ball filter to TIF images.
:::

::: {tab-item} Utilities
- [**utils_agg_files**](unravel.utilities.aggregate_files_from_sample_dirs): Aggregate files from sample directories.
- [**utils_prepend**](unravel.utilities.prepend_conditions): Prepend conditions to files using sample_key.csv.
- [**utils_rename**](unravel.utilities.rename): Rename files.
:::

::::

:::::{admonition} All commands
:class: note dropdown

::::{tab-set}

:::{tab-item} Registration
- [**reg_prep**](unravel.register.reg_prep): Prepare registration (resample the autofluo image to lower res).
- [**reg**](unravel.register.reg): Perform registration (e.g., register the autofluo image to an average template).
- [**reg_affine_initializer**](unravel.register.affine_initializer): Part of reg. Roughly aligns the template to the autofl image.
- [**reg_check**](unravel.register.reg_check): Check registration (aggregate the autofluo and warped atlas images).
- [**reg_check_brain_mask**](unravel.register.reg_check_brain_mask): Check brain mask for over/under segmentation.
:::

:::{tab-item} Warping
- [**warp_to_atlas**](unravel.warp.to_atlas): Warp full res tissue space images to atlas space.
- [**warp_to_fixed**](unravel.warp.to_fixed): Warp full res tissue space images to fixed img space and unpad.
- [**warp_to_native**](unravel.warp.to_native): Warp images to native img space, unpad, and scale to full res.
- [**warp_points_to_atlas**](unravel.warp.points_to_atlas): Warp cell centroids in tissue space to atlas space.
- [**warp**](unravel.warp.warp): Warp between moving and fixed images (these have 15% padding from reg)
:::

:::{tab-item} Segmentation
- [**seg_copy_tifs**](unravel.segment.copy_tifs): Copy TIF images (copy select tifs to target dir for training ilastik).
- [**seg_brain_mask**](unravel.segment.brain_mask): Create brain mask (segment resampled autofluo tifs).
- [**seg_ilastik**](unravel.segment.ilastik_pixel_classification): Perform pixel classification w/ Ilastik to segment features of interest.
- [**seg_labels_to_masks**](unravel.segment.labels_to_masks): Convert each label to a binary .nii.gz. 
:::

:::{tab-item} Voxel-wise stats
- [**vstats_apply_mask**](unravel.voxel_stats.apply_mask): Apply mask to image (e.g., nullify artifacts or isolate signals).
- [**vstats_prep**](unravel.voxel_stats.vstats_prep): Prepare immunofluo images for voxel statistics (e.g., background subtract and warp to atlas space).
- [**vstats_z_score**](unravel.voxel_stats.z_score): Z-score images.
- [**vstats_whole_to_avg**](unravel.voxel_stats.whole_to_LR_avg): Average left and right hemispheres together.
- [**vstats_hemi_to_avg**](unravel.voxel_stats.hemi_to_LR_avg): If left and right hemispheres were processed separately (less common), average them together.
- [**vstats**](unravel.voxel_stats.vstats): Compute voxel statistics.
- [**vstats_mirror**](unravel.voxel_stats.mirror): Flip and optionally shift content of images in atlas space.
:::

:::{tab-item} Cluster-wise stats
- [**cstats_fdr_range**](unravel.cluster_stats.fdr_range): Get FDR q value range yielding clusters.
- [**cstats_fdr**](unravel.cluster_stats.fdr): FDR-correct 1-p value map → cluster map.
- [**cstats_mirror_indices**](unravel.cluster_stats.recursively_mirror_rev_cluster_indices): Recursively mirror cluster maps for validating clusters in left and right hemispheres.
- [**cstats_validation**](unravel.cluster_stats.validation): Validate clusters w/ cell/label density measurements.
- [**cstats_summary**](unravel.cluster_stats.summary): Summarize info on valid clusters (run after cluster_validation).
- [**cstats_org_data**](unravel.cluster_stats.org_data): Organize CSVs from cluster_validation.
- [**cstats_group_data**](unravel.cluster_stats.group_bilateral_data): Group bilateral cluster data.
- [**cstats**](unravel.cluster_stats.cstats): Compute cluster validation statistics.
- [**cstats_index**](unravel.cluster_stats.index): Make a valid cluster map and sunburst plots.
- [**cstats_brain_model**](unravel.cluster_stats.brain_model): Make a 3D brain model from a cluster map (for DSI studio).
- [**cstats_table**](unravel.cluster_stats.table): Create a table of cluster validation data.
- [**cstats_prism**](unravel.cluster_stats.prism): Generate CSVs for bar charts in Prism.
- [**cstats_legend**](unravel.cluster_stats.legend): Make a legend of regions in cluster maps.
- [**cstats_sunburst**](unravel.cluster_stats.sunburst): Create a sunburst plot of regional volumes.
- [**cstats_find_incongruent_clusters**](unravel.cluster_stats.find_incongruent_clusters): Find clusters where the effect direction does not match the prediction of cstats_fdr (for validation of non-directional p value maps).
- [**cstats_crop**](unravel.cluster_stats.crop): Crop clusters to a bounding box.
- [**cstats_mean_IF**](unravel.cluster_stats.mean_IF): Compute mean immunofluo intensities for each cluster.
- [**cstats_mean_IF_summary**](unravel.cluster_stats.mean_IF_summary): Plot mean immunofluo intensities for each cluster.
- [**effect_sizes**](unravel.cluster_stats.effect_sizes.effect_sizes): Calculate effect sizes for clusters.
- [**effect_sizes_sex_abs**](unravel.cluster_stats.effect_sizes.effect_sizes_by_sex__absolute): Calculate absolute effect sizes by sex.
- [**effect_sizes_sex_rel**](unravel.cluster_stats.effect_sizes.effect_sizes_by_sex__relative): Calculate relative effect sizes by sex.
:::

:::{tab-item} Region-wise stats
- [**rstats**](unravel.region_stats.rstats): Compute regional cell counts, regional volumes, or regional cell densities.
- [**rstats_summary**](unravel.region_stats.rstats_summary): Summarize regional cell densities.
- [**rstats_mean_IF**](unravel.region_stats.rstats_mean_IF): Compute mean immunofluo intensities for regions.
- [**rstats_mean_IF_in_seg**](unravel.region_stats.rstats_mean_IF_in_segmented_voxels): Compute mean immunofluo intensities in segmented voxels.
- [**rstats_mean_IF_summary**](unravel.region_stats.rstats_mean_IF_summary): Plot mean immunofluo intensities for regions.
:::

:::{tab-item} Image I/O
- [**io_metadata**](unravel.image_io.metadata): Save raw voxel dimensions in microns and image dimensions to parameters/metadata.txt. 
- [**io_img**](unravel.image_io.io_img): Image I/O operations.
- [**io_nii_info**](unravel.image_io.nii_info): Print info about NIfTI files.
- [**io_nii_hd**](unravel.image_io.nii_hd): Print NIfTI headers.
- [**io_nii**](unravel.image_io.io_nii): NIfTI I/O operations (binarize, convert data type, scale, etc).
- [**io_reorient_nii**](unravel.image_io.reorient_nii): Reorient NIfTI files.
- [**io_nii_to_tifs**](unravel.image_io.nii_to_tifs): Convert NIfTI files to TIFFs.
- [**io_nii_to_zarr**](unravel.image_io.nii_to_zarr): Convert NIfTI files to Zarr.
- [**io_zarr_to_nii**](unravel.image_io.zarr_to_nii): Convert Zarr format to NIfTI.
- [**io_h5_to_tifs**](unravel.image_io.h5_to_tifs): Convert H5 files to TIFFs.
- [**io_tif_to_tifs**](unravel.image_io.tif_to_tifs): Convert TIF to TIFF series.
- [**io_img_to_npy**](unravel.image_io.img_to_npy): Convert images to Numpy arrays.
- [**io_points_to_img**](unravel.image_io.points_to_img): Populate an empty image with point coordinates
- [**io_img_to_points**](unravel.image_io.img_to_points): Convert and image into points coordinates
:::

:::{tab-item} Image tools
- [**img_avg**](unravel.image_tools.avg): Average NIfTI images.
- [**img_unique**](unravel.image_tools.unique_intensities): Find unique intensities in images.
- [**img_max**](unravel.image_tools.max): Print the max intensity value in an image.
- [**img_bbox**](unravel.image_tools.bbox): Compute bounding box of non-zero voxels in an image.
- [**img_spatial_avg**](unravel.image_tools.spatial_averaging): Perform spatial averaging on images.
- [**img_rb**](unravel.image_tools.rb): Apply rolling ball filter to TIF images.
- [**img_DoG**](unravel.image_tools.DoG): Apply Difference of Gaussian filter to TIF images.
- [**img_pad**](unravel.image_tools.pad): Pad images.
- [**img_resample**](unravel.image_tools.resample): Resample images.
- [**img_extend**](unravel.image_tools.extend): Extend images (add padding to one side).
- [**img_transpose**](unravel.image_tools.transpose_axes): Transpose image axes.
- [**img_resample_points**](unravel.image_tools.resample_points): Resample a set of points [and save as an image].
:::

:::{tab-item} Atlas tools
- [**atlas_relabel**](unravel.image_tools.atlas.relabel_nii): Relabel atlas IDs.
- [**atlas_wireframe**](unravel.image_tools.atlas.wireframe): Make an atlas wireframe.
:::

:::{tab-item} Utilities
- [**utils_get_samples**](unravel.utilities.get_samples): Test --pattern and --dirs args of script that batch process sample?? dirs.
- [**utils_agg_files**](unravel.utilities.aggregate_files_from_sample_dirs): Aggregate files from sample directories.
- [**utils_agg_files_rec**](unravel.utilities.aggregate_files_recursively): Recursively aggregate files.
- [**utils_prepend**](unravel.utilities.prepend_conditions): Prepend conditions to files using sample_key.csv.
- [**utils_rename**](unravel.utilities.rename): Rename files.
- [**utils_toggle**](unravel.utilities.toggle_samples): Toggle sample?? folders for select batch processing.
- [**utils_clean_tifs**](unravel.utilities.clean_tif_dirs): Clean TIF directories (no spaces, move non-tifs).
- [**utils_points_compressor**](unravel.utilities.points_compressor): Pack or unpack point data in a CSV file or summarize the number of points per region.
:::

::::

:::::


:::{admonition} More info on commands
:class: note dropdown
unravel_commands runs ./\<repo_root_dir\>/unravel/unravel_commands.py

Its help guide is here: {py:mod}`unravel.unravel_commands` 

Commands are defined in the `[project.scripts]` section of the [pyproject.toml](https://github.com/b-heifets/UNRAVEL/blob/main/pyproject.toml) in the root directory of the UNRAVEL repository (repo).

If new commands are added to run new scripts (a.k.a. modules), reinstall the unravel package with pip. 

```bash
cd <path to the root directory of the UNRAVEL repo>
pip install -e .
```
:::

---

## Set up

Recommended steps to set up for analysis:

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

### Add images to sample?? directories 

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

Paths to each experiment directory may be passed into scripts using the -d flag for batch processing

This is useful if there is not enough storage on a single drive. 

Also, spreading data across ~2-4 external drives allows for faster parallel processing (minimizes i/o botlenecks) 

If SSDs are used, distrubuting data may not speed up processing as much. 
```

### Log exp paths, commands, etc.
:::{admonition} Make an exp_notes.txt
:class: tip dropdown
This helps with keeping track of paths, commands, etc..
```bash
cd <path/to/dir/with/sample?? folders>
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

### Make a sample_key.csv: 

It should have these columns:
   * dir_name,condition
   * sample01,control
   * sample02,treatment
   * ...

### Defining Common Variables for Command Arguments
:::{admonition} To simplify running commands, define common variables in a shell script (e.g., env_var.sh).
:class: note dropdown
* For example, $BASE is global variable representing the path to the main experiment folder, a place to aggregate analyses and sample?? folders
* Example: $BASE represents the main experiment folder where analyses and sample?? folders (or condition folders with sample?? folders) are stored.
* Source the script to load variables in each terminal session
* Copy /UNRAVEL/unravel/env_var.sh to your experiment directory and update each variable with a code editor (e.g., **[VS Code](https://code.visualstudio.com/download)** or **[nano](https://www.youtube.com/watch?v=DLeATFgGM-A)**)
* Using your editor, add this line to your terminal config file (.bashrc or .zshrc) to easily load variables:
```bash
alias exp=". /path/to/env_var.sh"  # Update the path. Use a short name for `exp`.
```
```bash
# Reopen the terminal or source your terminal config file to apply changes
. ~/.bashrc  # or . ~/.zshrc

# Run the alias before using commands
exp

# Echo a variable to see its value:
echo $DIRS  # This variable contains a space-separated list of paths to sample?? folders or directories containing them (for batch processing with `-d`)

# Example:
utils_get_samples -d $DIRS  # Finds all sample?? folders in the paths from $DIRS.
```
:::


### Optional: clean tifs
   * If raw data is in the form of a tif series, consider running: 
```bash
utils_clean_tifs -t <path to directories with tifs relative to ./sample?? folders> -m
```
   * This will remove spaces from files names and move files other than *.tif to the parent directory

<br>

---


## Analysis steps

Overview of voxel-wise analyses followed by cluster validation:

:::{mermaid}
flowchart TD
    A(((LSFM))) 
    A --> B[3D autofluorescence image]
    B --> C(Registration to an average template brain) 
    A --> D[3D immunofluorescence image]
    D --> E(Remove autofluorescence from IF images)
    C --> F(Warp IF images to atlas space)
    E --> F
    F --> G(Preprocess IF images: z-scoring, smoothing, and averaging left/right sides)
    G --> H(Voxel-wise statistics)
    H --> I(FDR correction of 1-p value maps)
    I --> J(Warp significant voxel clusters to tissue space)
    J --> K(Validate clusters using cell/label density measurements)
    D --> L(Segment c-Fos+ cells or other features of interest with Ilastik)
    L --> K
:::

---

### Registration
:::{mermaid}
flowchart TD
    A(((LSFM))) 
    A --> B[Stitch z-stacks if necessary]
    B --> C(io_metadata: Save raw voxel dimentions in microns to ./sample??/parameters/metadata.txt)
    C --> D(reg_prep: Resample autofluorescence images to 50 µm resolution for registration)
    D --> E(seg_copy_tifs: Copy select slices from 50 µm autofl images to create brain masks using Ilastik)
    E --> F(Train Ilastik using pixel classification to segment autofl brains)
    F --> G(seg_brain_mask: Generate autofl brain masks with Ilastik and apply them to the 50 µm images)
    G --> H(Optionally use 3D Slicer to make the masked autofl image and mask better match the average template)
    H --> I(reg: Register the template brain with the masked autofl images and warp the atlas)
    I --> J(reg_check: Aggregate padded autofl images and warped atlas images from reg)
    J --> K(Assess registration quality in FSLeyes and refine if necessary by repeating the 3D Slicer step, etc.)

:::

#### `io_metadata`
{py:mod}`unravel.image_io.metadata`
* Extract or specify x and z voxel sizes in microns (saves to ./sample??/parameters/metadata.txt). 
* You can add these resolutions to env_var.sh as global variables (e.g., $XY and $Z) and load them before running commands with: `source path/to/env_var.sh`
* **[Guide on defining common command arguments in env_var.sh](https://b-heifets.github.io/UNRAVEL/guide.html#defining-common-variables-for-command-arguments)**
* For batch processing, run the io_metadata command from a directory containing sample?? folders, within a sample?? folder, or use -d to pass in a list of paths to sample folders or directories containing sample folders.
```bash
# To specify x and z voxel sizes in microns, use the -x and -z flags.
io_metadata -i <path to image or directory with TIFFs relative to sample??/> -x $XY -z $Z [-d $DIRS] # Remove square brackets from optional arguments
# If env_var.sh is not used, pass in the voxel sizes like this: -x 3.5232 -z 6.

# If -x and -z are omitted, io_metadata will attempt to extract this information from the image metadata.
io_metadata -i <rel_path/full_res_img> [-d $DIRS]
# 'rel_path' refers to the relative path from within the sample?? folders.
# Glob patterns can be used for -i (e.g., *.czi).
```

#### `reg_prep`
{py:mod}`unravel.register.reg_prep` 
* Prepare autofluorescence images for registration (resample them to 50 µm isotropic resolution and save to ./sample??/reg_inputs/)
```bash
reg_prep -i <rel_path/image> [-d $DIRS] # -i options: tif_dir, .czi, .h5, .zarr, or .tif (e.g., *.czi)
# If using *.czi, by default the first channel is used (--channel 0), since that is usually the autofluo channel
```

#### `seg_copy_tifs`
{py:mod}`unravel.segment.copy_tifs`
* Copy resampled autofluo .tif files from each sample for making a brain mask with ilastik
* In the example below -s 0000 0005 0050 means that the 1st, 6th, and 51st tif will be copied to the target directory
* The target directory is the current working directory unless -td is used to specify an output path.
```bash
seg_copy_tifs -i reg_inputs/autofl_??um_tifs -s 0000 0005 0050 [-td brain_mask] [-d $DIRS]  
```

#### Train an Ilastik project

[Pixel classification documentation](https://www.ilastik.org/documentation/pixelclassification/pixelclassification)

::: {admonition} Setting up Ilastik for batch processing
:class: note
* [Install Ilastik](https://www.ilastik.org/download)
```bash
# Add this to your ~/.bashrc or ~/.zshrc terminal config file:
export PATH=/usr/local/ilastik-1.4.0.post1-Linux:$PATH   # Update the path and version

# Optional: add a shortcut command for launching Ilastik via the terminal
alias ilastik=run_ilastik.sh  # This is for Linux (update the relative path if needed)

# Ilastik executable files for each OS:
#     - Linux: /usr/local/ilastik-1.3.3post3-Linux/run_ilastik.sh
#     - Mac: /Applications/Ilastik.app/Contents/ilastik-release/run_ilastik.sh
#     - Windows: C:\Program Files\ilastik-1.3.3post3\run_ilastik.bat

# Source your terminal config file for these edits to take effect: 
. ~/.bashrc  # Or close and reopen the terminal
```
:::

::: {admonition} Training Ilastik
:class: note

**Launch Ilastik** 
   - Either double click on the application or run: `ilastik`

1. **Input Data**  
   Drag training slices into the ilastik GUI (e.g., from a dir w/ 3 slices per sample and > 2 samples per condition)
   `ctrl+A` -> right-click -> Edit shared properties -> Storage: Copy into project file -> Ok  

2. **Feature Selection**  
   Select Features... -> select all features (`control+a`) or an optimized subset (faster but less accurate).
   Optional: to find an optimal subset of features, select all features, train Ilastik, turn off Live Updates, click Suggest Features, select a subset, and refine training.

3. **Training**  
   - ***Brightness/contrast***: select the gradient button and click and drag in the image (faster if zoomed in)
   - ***Zoom***: `control/command + mouse wheel scroll`, `control/command + 2 finger scroll`, or `-` and `+` (i.e., `shift + =`)
   - ***Pan***: `shift` + `left click and drag` or `click mouse wheel and drag`
   - With `label 1` and the `brush tool` selected, paint on c-Fos+ cells or another feature of interest
   - With `label 2` and the `brush tool` selected, paint on the background (e.g., any pixel that is not a cell)
   - Turn on `Live Update` to preview pixel classification (faster if zoomed in) and refine training (e.g., if some cells are classified as background, paint more cells with label 1).
     - `s` will toggle the segmentation on and off.
     - `p` will toggle the prediction on and off.
     - Toggle eyes to show/hide layers and/or adjust transparency of layers. 

   - Change `Current View` to see other training slices. Check segmentation for these and refine as needed.
   - Save the project in the experiment summary folder and close if using this script to run ilastik in headless mode for segmenting all images.

**Notes**
- If you want to go back to steps 1 & 2, turn Live Updates off
- It is possible at add extra labels with `a` (e.g., if you want to segment somata with one label and axons with another label)
- If you accidentally press `a`, turn off Live Updates and press `x` next to the extra label to delete it.
- If the segmentation for label 1 fuses neighboring cells, draw a thin line in between them with label 2. 
:::


#### `seg_brain_mask`
{py:mod}`unravel.segment.brain_mask`
* Makes reg_inputs/autofl_??um_brain_mask.nii.gz and reg_inputs/autofl_??um_masked.nii.gz for ``reg``
```bash
seg_brain_mask -ie <path/ilastik_executable> -ilp <path/trained_ilastik_project.ilp> [-d $DIRS]
```

:::{admonition} Making the autofluorescence image better match the average template image
:class: hint
* seg_brain_mask zeros out voxels outside of the brain. This prevents the average template (moving image) from being pulled outward during registration (reg). 
* If non-zero voxles outside the brain remain and are affecting reg quality, use 3D slicer to zero them out by painting in 3D (segmentation module). 
* If there is missing tissue, use 3D slicer to fill in gaps. 
:::

:::{todo}
Add tutorial for 3D slicer
:::

#### `reg`
{py:mod}`unravel.register.reg`
* Register an average template brain/atlas to a resampled autofluo brain.

```{admonition} Determining the 3 letter orientation code
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
reg -m <path/template.nii.gz> -bc -sm 0.4 -ort <3 letter orientation code> -m2 <path/atlas_CCFv3_2020_30um.nii.gz> [-d $DIRS]

# Example if using env_var.sh (assuming an RPS orientation):
reg -m $TEMPLATE -bc -pad -sm 0.4 -ort RPS -a $ATLAS -d $DIRS

# -bc performs N4 bias field correction to make image intensities more uniform
# -sm smooths the autofluo image by the amount specified
# If you want to use an unmasked autofluo image, provide: -mas None -f reg_inputs/autofl_50um.nii.gz. Other commands alos assume that a masked autofluo image was used, so check each help guide for default arguments.
```

:::{admonition} If sample orientations vary
:class: tip dropdown
Make a ./sample??/parameters/ort.txt with the 3 letter orientation for each sample and run:
```bash
for d in $DIRS ; do cd $d ; for s in sample?? ; do reg -m $TEMPLATE -bc -pad -sm 0.4 -ort $(cat $s/parameters/ort.txt) -a $ATLAS -v -d $PWD/$s ; done ; done 
```
:::

#### `reg_check`
{py:mod}`unravel.register.reg_check`
* Check registration by copying these images from each sample??/reg_ouputs folder to a target directory: 
    * autofl_??um_masked_fixed_reg_input.nii.gz
    * atlas_in_tissue_space.nii.gz
```bash
reg_check [-td reg_results] [-d $DIRS]  # Default for -td: copy images to the current dir.
# The default warped atlas from reg is atlas_CCFv3_2020_30um_in_tissue_space.nii.gz (in ./sample??/.reg_outputs). Use -wa <image_name.nii.gz> to set this.

```
* View these images with [FSLeyes](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FSLeyes) [docs](https://open.win.ox.ac.uk/pages/fsl/fsleyes/fsleyes/userdoc/index.html)
* FSLeyes might not work in Windows without additional set up: [Installation on Windows](https://fsl.fmrib.ox.ac.uk/fsl/docs/#/install/windows)

```{figure} _static/FSLeyes_autofl_image_from_reg.jpg
:alt: Batch stitching settings
:height: 800px
:align: center
Use FSLeyes to view the autofluo image from `reg` (sample??/reg_ouputs/autofl_50um_masked_fixed_reg_input.nii.gz).
```

```{figure} _static/FSLeyes_atlas_warped_to_tissue_from_reg.jpg
:alt: Batch stitching settings
:height: 800px
:align: center
Use FSLeyes to view the atlas warped to the the tissue (sample??/reg_ouputs/atlas_CCFv3_2020_30um_in_tissue_space.nii.gz)
```

::: {admonition} Setting up Allen brain atlas coloring in FSLeyes
:class: note
* Add `UNRAVEL/_other/fsleyes_luts/ccfv3_2020.lut` to the following location:
   * **Linux**: `/home/<your_username>/.config/fsleyes/luts/ccfv3_2020.lut`
   * **MacOS**: `/usr/local/fsl/fslpython/envs/fslpython/lib/python3.8/site-packages/fsleyes/assets/luts/ccfv3_2020.lut`
   * **Windows**: `C:\Users\<your_username>\AppData\Roaming\fsleyes\luts\ccfv3_2020.lut`

* On **MacOS**, run the following command to add write permissions to the LUT folder:
```bash
sudo chmod a+w /usr/local/fsl/fslpython/envs/fslpython/lib/python3.8/site-packages/fsleyes/assets/luts
```
* On **MacOS**, edit `order.txt` to include `ccfv3_2020.lut`.
* To remove other LUTs, move them up a directory level, but keep `random.lut` in place.
* Open `atlas_CCFv3_2020_30um.nii.gz` in FSLeyes.
* Select the atlas and change "3D/4D volume" to "Label image."
* Switch the lookup table from `random` to `ccfv3_2020`.
* Click the circle icon at the top to convert the atlas to a wireframe view.
* If you don't want to select the LUT every time, make a copy of `random.lut` and replace its contents with those of `ccfv3_2020.lut`.
:::


### Voxel-wise stats
:::{mermaid}
flowchart TD
    A(((LSFM))) 
    A --> B[Stitch z-stacks if required]
    B --> C(vstats_prep: Optionally remove autofluorescence and warp immunofluo images to atlas space)
    C --> D(vstats_z_score: Optionally z-score IF images from each brain individually)
    D --> E(utils_agg_files: Aggregate atlas-space IF images from all sample folders into the current directory)
    E --> F(vstats_whole_to_avg: Optionally smooth image and average left/right sides)
    F --> G(Check inputs for vstats: Open IF images and the atlas in FSLeyes to confirm aligment with the atlas and other IF images)
    G --> H(Prep inputs for vstats: Add IF images to the current directory, without other .nii.gz files)
    H --> I(utils_prepend: Prepend a one-word condition to each IF image)
    I --> J(For ANOVA designs, run fsl and set up the design. If two groups are present, proceed to the next step)
    J --> K(vstats: Run voxel-wise analyses using FSL's randomise tool)
    K --> L(View 1-p value maps in FSLeyes and consult 'Cluster-wise stats' for multiple comparisons correction and cluster validation)
:::

#### `vstats_prep`
{py:mod}`unravel.voxel_stats.vstats_prep`
* Preprocess immunofluo images and warp them to atlas space for voxel-wise statistics.
```bash
# Example with rolling ball background subtration (pixel radius of 4):
vstats_prep -i cfos -o cFos_rb4_atlas_space.nii.gz -rb 4 -a $ATLAS [-d $DIRS]

# Usage:
vstats_prep -i <rel_path/image> -o cFos_rb4_atlas_space.nii.gz -a $ATLAS [-sa 3] [-rb 4] [--channel 1] [-d $DIRS]
# --channel is for .czi images (1 is the second channel)
```
:::{admonition} Info on background subtraction
:class: tip dropdown
* Removing autofluorescence from immunolabeling improves the sensitivity of voxel-wise comparisons. 
* Use -sa 3 for 3x3x3 spatial averaging if there is notable noise from voxel to voxel. 
* Use -rb for rolling ball background subtraction. 
* Use a smaller rolling ball radius if you want to preserve punctate signal like c-Fos+ nuclei (e.g., 4)
* Use a larger rolling ball radius if you want to preserve more diffuse signal (e.g., 20).
* The radius should be similar to the largest feature that you want to preserve. 

You can test parameters for background subtraction with: 
* {py:mod}`unravel.image_tools.spatial_averaging`
* {py:mod}`unravel.image_tools.rb`
    * Copy a tif to a test dir for this (e.g., with `seg_copy_tifs`)
    * Use {py:mod}`unravel.image_io.io_img` to create a tif series
:::

```{figure} _static/FSLeyes_Ai14_image_in_CCFv3_30um_space.jpg
:alt: Batch stitching settings
:height: 800px
:align: center
Use FSLeyes to view the fluorescently labeled image in atlas space.
```

#### `vstats_z_score`
{py:mod}`unravel.voxel_stats.z_score`
* Z-score atlas space images using tissue masks (from brain_mask) and/or an atlas mask.
```bash
# Z-scoring using the brain mask (-i and -tmas paths are relative to the sample?? folder)
vstats_z_score -i atlas_space/sample??_cFos_rb4_atlas_space.nii.gz [-d $DIRS] 

# Z-scoring using an atlas mask
vstats_z_score -i 'atlas_space/*.nii.gz' -amas $MASK [-d $DIRS] 

# Using a tissue mask and an atlas mask
vstats_z_score -i 'atlas_space/*.nii.gz' -tmas reg_inputs/autofl_50um_brain_mask.nii.gz -amas $MASK [-d $DIRS] 
```

#### `utils_agg_files`
{py:mod}`unravel.utilities.aggregate_files_from_sample_dirs`
* Aggregate pre-processed immunofluorescence (IF) images for voxel-wise stats
```bash
utils_agg_files -i atlas_space/*_cFos_rb4_atlas_space_z.nii.gz [-td path/target_dir] [-d $DIRS]
```

#### `vstats_whole_to_avg`
{py:mod}`unravel.voxel_stats.whole_to_LR_avg`
* Smooth and average left and right hemispheres together
```bash
# Run this in the folder with the .nii.gz images to process
vstats_whole_to_avg -k 0.1 --parallel -v  # A 0.05 mm - 0.1 mm kernel radius is recommended for smoothing

# Process all *.nii.gz files in the current directory with no smoothing:
vstats_whole_to_avg [-tp] [-amas $MASK] # Provide -tp for parallel processing.

# Process files matching the pattern with smoothing:
vstats_whole_to_avg -i '*_cFos_rb4_atlas_space_z.nii.gz.nii.gz' -k 0.1 [-tp] [-amas $MASK]
# A 0.1 mm kernel radius is recommended for smoothing (-k)
```

:::{seealso} 
{py:mod}`unravel.voxel_stats.hemi_to_LR_avg`
:::

::: {admonition} Setting up voxel-wise stats
:class: note

1. **Create a vstats folder and subfolders for each analysis**:  
   - Name subfolders succinctly (this name is added to other folder and file names).

2. **Generate and add .nii.gz files to vstats subfolders**:
   - Input images are from ``vstats_prep`` and may have been z-scored with ``vstats_z_score`` (we z-score c-Fos labeling as intensities are not extreme)
   - For bilateral data, left and right sides can be averaged with ``vstats_whole_to_avg`` (then use a unilateral hemisphere mask for ``vstats`` and ``cstats_fdr``).
   - We smooth data (e.g., with a 100 µm kernel) to account for innacuracies in registration
      - This can be performed with ``vstats_whole_to_avg`` or ``vstats``
   - Prepend filenames with a one word condition (e.g., `drug_sample01_atlas_space_z.nii.gz`).
      - Camel case is ok for the condition.
      - ``utils_prepend`` can add conditions to filenames.
      - Group order is alphabetical (e.g., drug is group 1 and saline is group 2).
   - View the images in [FSLeyes](https://open.win.ox.ac.uk/pages/fsl/fsleyes/fsleyes/userdoc/index.html) to ensure they are aligned with the atlas and the sides are correct.
   - Other .nii.gz images unrelated to voxel-wise analyses should be excluded from the vstats subfolder.

3. **Determine Analysis Type**:  
   - If there are 2 groups, ``vstats`` may be used after pre-processing. 
   - If there are more than 2 groups, prepare for an ANOVA as described below

#### Vstats outputs
- **T-test outputs**:  
    - `vox_p_tstat1.nii.gz`: Uncorrected p-values for tstat1 (group 1 > group 2).
    - `vox_p_tstat2.nii.gz`: Uncorrected p-values for tstat2 (group 1 < group 2).

- **ANOVA outputs**:  
    - `vox_p_fstat1.nii.gz`: Uncorrected p-values for fstat1 (1st contrast, e.g., drug vs. saline).
    - `vox_p_fstat2.nii.gz`: Uncorrected p-values for fstat2 (2nd contrast, e.g., context1 vs. context2).
    - `vox_p_fstat3.nii.gz`: Uncorrected p-values for fstat3 (3rd contrast, e.g., interaction).

#### Example: Preparing for an ANOVA
1. **Setup Design Matrix**:
   - For an ANOVA, create `./vstats/vstats_dir/stats/design/`.
   - Open terminal from `./stats` and run: `fsl`.
   - Navigate to `Misc -> GLM Setup`.

2. **GLM Setup Window**:
   - Select `Higher-level / non-timeseries design`.
   - Set `# inputs` to the total number of samples.

3. **EVs Tab in GLM Window**:
   - Set `# of main EVs` to 4.
   - Name EVs (e.g., `EV1 = group 1`).
   - Set Group to 1 for all.

4. **Design Matrix**:
   - Under `EV1`, enter 1 for each subject in group 1 (1 row/subject). EV2-4 are 0 for these rows.
   - Under `EV2`, enter 1 for each subject in group 2, starting with the row after the last row for group 1.
   - Follow this pattern for EV3 and EV4.

5. **Contrasts & F-tests Tab in GLM Window**:
   - Set `# of Contrasts` to 3 for a 2x2 ANOVA: 
     - `C1`: `Main_effect_<e.g.,drug>` 1 1 -1 -1 (e.g., EV1/2 are drug groups and EV3/4 are saline groups).
     - `C2`: `Main_effect_<e.g., context>` 1 -1 1 -1 (e.g., EV1/3 were in context1 and EV2/4 were in context2).
     - `C3`: `Interaction` 1 -1 -1 1.
   - Set `# of F-tests` to 3:
     - `F1`: Click upper left box.
     - `F2`: Click middle box.
     - `F3`: Click lower right box.

6. **Finalize GLM Setup**:
   - In the GLM Setup window, click `Save`, then click `design`, and click `OK`.

7. **Run Voxel-wise Stats**:
   - From the vstats_dir, run: ``vstats``.

#### Background on FSL's randomise tool
- [FSL GLM Guide](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/GLM)
- [FSL Randomise User Guide](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Randomise/UserGuide)
:::

#### `vstats`
{py:mod}`unravel.voxel_stats.vstats`
* Run voxel-wise stats using FSL's randomise_parallel command
* Outputs saved in stats/
```bash
# Run this in the folder with the input IF images (the current directory name will be prepended to outputs)
vstats -mas $MASK -a $ATLAS [-p 18000] [-k 0.1]
# -p sets the number of permutations.
# -k is for smoothing if inputs have not yet been smoothed (-k is the kernel size in mm)
# See the vstats help for providing additional arguments to FSL's randomise_parallel
```

::: {admonition} Outputs from voxel-wise stats
:class: note
* Outputs in ./stats/
    * vox_p maps are uncorrected 1 - p value maps
    * tstat1: group1 > group2
    * tstat2: group2 > group1
    * fstat*: f contrast w/ ANOVA design (non-directional p value maps)
    * fstat1 corresponds to the first Contrast defined in step 5 above. 
:::



### Cluster-wise stats

flowchart TD
    A(vstats: Generates 1-p value maps named *vox_p*.nii.gz)
    A --> B(cstats_fdr_range: Input a 1-p map to find FDR q values that yield clusters)
    B --> C(cstats_fdr: Apply FDR correction on the 1-p map to identify clusters of significant voxels)
    C --> D(cstats_mirror_indices: For whole-brains, recursively mirror cluster maps in ./stats/)
    D --> E(seg_copy_tifs: Copy select full resolution TIFFs for Ilastik training)
    E --> F(seg_ilastik: Perform pixel classification with a trained Ilastik project)
    F --> G(cstats_validation: Warp clusters from atlas to full resolution tissue space, count cells, and calculate cluster volumes)
    G --> H(cstats_summary: Aggregate and analyze cluster validation data)

#### False discovery rate (FDR) correction

#### `cstats_fdr_range`
{py:mod}`unravel.cluster_stats.fdr_range`
* Outputs a list of FDR q values that yield clusters.
```bash
cstats_fdr_range -i <path/vox_p_tstat1.nii.gz> -mas $MASK
```

#### `cstats_fdr`
{py:mod}`unravel.cluster_stats.fdr`
* Perform FDR correction on a 1-p value map to define clusters
* Outputs are saved to a new folder in stats/ named after the input image and q value
```bash
cstats_fdr -i <path/vox_p_tstat1.nii.gz> -mas $MASK -q 0.05 0.01 0.001 [-ms 100] 
# For -q, copy the output from cstats_fdr_range
# For -ms, set the number of voxels for a cluster (e.g., 100 for c-Fos or 400 if labeling is sparse)

# Perform FDR correction on multiple directional 1-p value maps
for j in *_vox_p_*.nii.gz ; do q_values=$(cstats_fdr_range -mas $MASK -i $j) ; cstats_fdr -mas $MASK -i $j -q $q_values ; done

# ANOVAs output non-directioanl 1-p value maps. Optionally convert them into a directional cluster index:
q_values=$(cstats_fdr_range -i vox_p_fstat1.nii.gz -mas $MASK) ; cstats_fdr -i vox_p_fstat1.nii.gz -mas $MASK -o fstat1 -v -a1 Control_avg.nii.gz -a2 Deep_avg.nii.gz -q $q_values
# Make averaged images for each group (-a1 and -a2 args) with the img_avg command
```

#### `cstats_mirror_indices`
{py:mod}`unravel.cluster_stats.recursively_mirror_rev_cluster_indices`
* Recursively flip the content of rev_cluster_index.nii.gz images (to validate w/ clusters in left and right hemispheres)
* Run this in the ./stats/ folder to process all subdirs with reverse cluster maps (cluster IDs go from large to small)
```bash
# Use -m RH if a right hemisphere mask was used (otherwise use -m LH)
cstats_mirror_indices -m RH [-i glob_pattern]
```

#### Segmentation of full resolution IF images

**[Guide on training Ilastik](https://b-heifets.github.io/UNRAVEL/guide.html#train-an-ilastik-project)**

#### `seg_copy_tifs`
{py:mod}`unravel.segment.copy_tifs`
* Copy or extract full res tif files to a target dir for training Ilastik to segment labels of interest 
:::{tip} 
Copy/extract 3 slices from each sample, with at least 3 samples per condition.
:::
```bash
seg_copy_tifs -i <rel_path/raw_image> -s 0100 0500 1000 [-td ilastik_segmentation] [-d $DIRS]
# Default for target dir (-td) is current dir
# The name of the dir with full-res tifs can be passed in for -i
```

#### `seg_ilastik`
{py:mod}`unravel.segment.ilastik_pixel_classification`
* Segment features of interest (e.g., c-Fos+ cells) in full-resulution images using a trained Ilastik project (pixel classification)
```bash
seg_ilastik -ie <path/ilastik_executable> -ilp <path/ilastik_project.ilp> -i <rel_path to tif_dir or image> -o seg_dir --labels 1 [--rm_out_tifs] [--channel 1] [-d $DIRS]
# --labels is a space-separated list of labels to convert into binary .nii.gz images.
# --channel is for .czi images (1 is the second channel)
```


#### Cluster validation

#### `cstats_validation`
{py:mod}`unravel.cluster_stats.validation`
* Warps cluster index from atlas space to tissue space, crops clusters, applies segmentation mask, and quantifies cell or label densities
```bash
# Cell density measurements in all clusters
cstats_validation -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s  <rel_path/seg_img.nii.gz> [-d $DIRS]

# Label density measurements in select clusters
cstats_validation -m <path/rev_cluster_index_to_warp_from_atlas_space.nii.gz> -s  <rel_path/seg_img.nii.gz> -de label_density -c 1 3 4 [-d $DIRS]

# Use -n to save the cluster map in tissue space (-n rel_path/native_cluster_index.zarr). Slower than w/o saving.
# -inp nearestNeighbor is default, but for smoother clusters use multiLabel (slower)

# Processing multiple FDR q value thresholds and both hemispheres (assumes that cstats_mirror_indices has been run):
for q in 0.005 0.01 0.05 0.1 ; do for side in LH RH ; do cstats_validation  -m path/vstats/contrast/stats/contrast_vox_p_tstat1_q${q}/contrast_vox_p_tstat1_q${q}_rev_cluster_index_${side}.nii.gz -s rel_path/seg_img.nii.gz [-d $DIRS] ; done ; done
```

#### `cstats_summary`
{py:mod}`unravel.cluster_stats.summary`
* Aggregates and analyzes cluster validation data from `cstats_validation`
* Update parameters in /UNRAVEL/unravel/cstats/cluster_summary.ini and save it with the experiment
* group1 and group2 must match conditions in the sample_key.csv
```bash
# Usage if running directly after ``cstats_validation``
cstats_summary -c <path/cluster_summary.ini> -cvd 'psilocybin_v_saline_tstat1_q*' -vd <path/vstats_dir> -sk $SAMPLE_KEY --groups <group1> <group2> -hg <higher_group> [-d $DIRS]

# Usage if running after ``cstats_validation`` and ``cstats_org_data``:
cstats_summary -c <path/cluster_summary.ini> -sk $SAMPLE_KEY  --groups <group1> <group2> -hg <higher_group> [-d $DIRS]

# See the help guide for cstats_validation if you want to pool data using condition prefixes
```



### Region-wise stats

:::{mermaid}
flowchart TD
    A(((LSFM))) 
    A --> B[3D autofluorescence image]
    B --> C(Registration to an average template brain) 
    C --> D(Optional: warp_to_native: Warp the atlas to full-resolution tissue space and save as .zarr)
    A --> E[3D immunofluorescence image]
    E --> F(seg_copy_tifs & seg_ilastik: Segment c-Fos+ cells using Ilastik)
    F --> G(rstats: Perform regional cell counting and volume measurements)
    D --> G
    G --> H(utils_agg_files: Aggregate CSV outputs from rstats across all sample folders)
    H --> I(rstats_summary: Plot cell densities by region and summarize results)
:::

#### `rstats`
{py:mod}`unravel.region_stats.regional_cell_densities`
* Perform regional cell counting (TODO: add label density measurements)
```bash
# Usage if the atlas is already in native space from ``warp_to_native``:
rstats -s <rel_path/segmentation_image.nii.gz> -a <rel_path/native_atlas_split.nii.gz> -c Saline -t cell_densities [-d <paths to sample folders in the Saline group or the folders containing them>]

# Usage if the native atlas is not available; it is not saved (faster):
rstats -s rel_path/segmentation_image.nii.gz -m $SPLIT -c Saline -t cell_densities [-d <paths to sample folders in the Saline group or the folders containing them>]
```

Aggregate outputs from `rstats` with `utils_agg_files`.

#### `rstats_summary`
{py:mod}`unravel.region_stats.regional_cell_densities_summary`
* Plot cell densities for each region and summarize results.
* CSVs from `rstats` should be in the current directory
* CSV columns: 
    * Region_ID,Side,Name,Abbr,Saline_sample06,Saline_sample07,...,MDMA_sample01,...,Meth_sample23,...
```bash
# Usage for Tukey tests:
rstats_summary --groups Saline MDMA Meth -hemi <both l or r> [-y cell_density] [-div 10000]
# -div 10000 divides cells per cubic mm by 10000 (for plotting)
# -y is the y-axis label

# Usage for t-tests:
rstats_summary --groups Saline MDMA -hemi <both l or r>  -t t-test -c Saline [-alt two-sided] [-y cell_density] [-div 10000] 
```


### Example sample?? folder structure after analysis
```bash
.
├── atlas_space  # Dir with images warped to atlas space
├── cfos_seg_ilastik_1  # Example dir with segmentations from ilastik
├── clusters  # Dir with cell/label density CSVs from cstats_validation
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
│   ├── atlas_CCFv3_2020_30um.nii.gz  # Each atlas region has a unique intensity/ID
│   ├── atlas_CCFv3_2020_30um_split.nii.gz  # Intensities in the left hemisphere are increased by 20,000
│   ├── average_template_CCFv3_30um.nii.gz  # Average template brain that is aligned with the atlas
│   └── mask_CCFv3_2020_30um_RH_wo_root_ventricles_fibers_OB.nii.gz  # Right hemisphere mask that excludes undefined regions (root), ventricles, fiber tracts, and the olfactory bulb
├── check_reg  # run check_reg from here
├── brain_mask
│   ├── brain_mask.ilp  # Ilastik project trained with the pixel classification workflow to segment the brain in resampled autofluo images
│   ├── sample01_slice_0000.tif
│   ├── sample01_slice_0005.tif
│   ├── sample01_slice_0050.tif
│   ├── ...
│   └── sample04_slice_0050.tif
├── vstats  # Voxel-wise stats
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
│           │   └── ..._rev_cluster_index.nii.gz # cluster map (index) with cluster IDs going from large to small (input for cstats_validation)
│           ├── ...
│           └── Control_v_Treatment_vox_p_tstat2_q0.05
├── cstats  # cluster stats (validation)
│   ├── Control_v_Treatment_vox_p_tstat1_q0.005
│   │   ├── Control_sample01_cell_density_data.csv
│   │   ├── Control_sample02_cell_density_data.csv
│   │   ├── Treatment_sample03_cell_density_data.csv
│   │   └── Treatment_sample04_cell_density_data.csv
│   ├── ...
│   └── Control_v_Treatment_vox_p_tstat2_q0.05
└── rstats # regional stats
    ├── Control_sample01_regional_cell_densities.csv
    ├── ...
    └── Treatment_sample04_regional_cell_densities.csv
```

```{todo}
Add notes here on FSLeyes, ploting sunbursts, and viewing clusters in 3D. Prompt us when you get to this step (notes on Slack)

Also show the structure of data from cstats_validation and rstats_summary
```


### Other useful commands, etc.

#### `img_avg`
{py:mod}`unravel.image_tools.avg`

* Average *.nii.gz images (e.g., from `vstats`)
* Averaged images from each group can be used to convert non-directioanl 1 - p value maps into directional cluster indices with `cstats_fdr`
```bash
img_avg -i Control_*.nii.gz -o Control_avg.nii.gz
```