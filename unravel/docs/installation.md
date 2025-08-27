# Installation
* Please send questions/issues to [danrijs@stanford.edu](mailto:danrijs@stanford.edu), so we can improve UNRAVEL and/or its documentation
* If you are new to the terminal, please see the start of the [UNRAVEL guide](https://b-heifets.github.io/UNRAVEL/guide.html)


## TL;DR on Installation
* Activate a virtual environment in Python
```bash
# Installing UNRAVEL
git clone https://github.com/b-heifets/UNRAVEL.git
cd UNRAVEL
pip install -e .

# Updating UNRAVEL
git pull 
pip install -e . 
```

* Confirm that installation worked by running: 
```bash
unravel_commands -c  # or run: uc -c
# This should print common UNRAVEL commands

# For more info, run
uc -h 
```

* **[Download atlas/template files](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)**
    * This has an [iDISCO/LSFM-specific template](https://pubmed.ncbi.nlm.nih.gov/33063286/) that we warped to 30 µm [CCFv3 atlas](https://www.sciencedirect.com/science/article/pii/S0092867420304025) space
* **Required software:**
    * [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation) for voxel-wise stats, CLI tools, and viewing .nii.gz images with [FSLeyes](https://open.win.ox.ac.uk/pages/fsl/fsleyes/fsleyes/userdoc/index.html)
        * See below on setting this up by adding lines to a terminal configuration file (e.g., .bashrc or .zshrc)
        * Extra steps are required for Windows (even if the GUI does not work, commands may work ok and [ITK-SNAP](http://www.itksnap.org/pmwiki/pmwiki.php?n=Main.HomePage) instead of [FSLeyes](https://open.win.ox.ac.uk/pages/fsl/fsleyes/fsleyes/userdoc/index.html))
    * [Ilastik](https://www.ilastik.org/download.html) for segmenting features of interest
        * See below for .bashrc configuration
* **Recommended software:**
    * [3D Slicer](https://download.slicer.org/) for 3D painting to make brains more like the average template (improves registration)
    * [DSI Studio](https://dsi-studio.labsolver.org/download.html) for 3D brain models.
    * [Flourish](https://app.flourish.studio/login) for sunburst plots (free web app)
    * [Visual Studio Code](https://code.visualstudio.com/) for viewing source code, debugging, editing files (e.g., .bashrc), etc.
        * Enstall the [Python extension](https://code.visualstudio.com/docs/languages/python)

## TL;DR on Getting Started
* Review the [UNRAVEL guide](https://b-heifets.github.io/UNRAVEL/guide.html) for analysis steps.
* Add raw stitched LSFM data into sample?? folders (e.g., sample01, sample02, ...).
* Try out the command `utils_get_samples` to test out batch processing of sample?? folders.
* The first command in the workflow is `io_metadata`.
* Each command has a help guide with inputs, outputs, next steps, etc.
* For example, run `io_metadata -h` to get started.

--- 

## Installing UNRAVEL on Linux or WSL

:::{admonition} Setting Up Windows Subsystem for Linux (WSL)
:class: hint dropdown

If you're new to WSL, watch the first few minutes of [this video](https://www.youtube.com/watch?v=-atblwgc63E). After installation, refer to this [tutorial](https://www.youtube.com/watch?v=i547sSXhq0E) for navigating your files.

### Installing WSL:
1. Open the Start menu, search for PowerShell, and right-click to run as Administrator.
2. Run:
    ```powershell
    wsl --install  # Installs Ubuntu by default
    ```
3. Restart your computer when prompted.
4. After the reboot, WSL will be ready. Open PowerShell and type:
    ```powershell
    wsl
    ```
5. Follow the prompts to set up your username and password.

:::note
To enable copy/paste in PowerShell or WSL, go to the top-left icon --> Properties --> Edit Options --> check "Use Ctrl+Shift+C/V as Copy/Paste" --> OK.

If you install FSL (includes FSLeyes) and Ilastik for linux for use via WSL, the graphic user interface may not work. If that is an issue, try installing the Windows versions.
:::

### Running Linux Applications in WSL

If you install graphical applications like **FSL** (which includes FSLeyes) or **Ilastik** for Linux in WSL, the graphical user interface may not work out of the box. 

* **Option 1**: Install the Windows versions of these tools for GUI support (the linux versions could still be used for headless processing via commands in WSL)
* **Option 2**: Set up a graphical server, such as **VcXsrv**, to enable GUIs for Linux applications running in WSL.
    * For example, here are detailed steps to set up FSL on Windows: [Installation on Windows](https://fsl.fmrib.ox.ac.uk/fsl/docs/#/install/windows)
:::


1. **Open a terminal**

2. **Install [venv](https://docs.python.org/3/library/venv.html), [pyenv](https://github.com/pyenv/pyenv), [conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html), or other tool(s) to manage Python versions and create a virtual environment:**

:::{admonition} Setting up a virtual environment for installing python dependencies with venv
:class: hint dropdown
1. Install Python 3.11 if it's not already installed:
    - For Linux and WSL:
    ```bash
    sudo apt-get update
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
    ```
    - For macOS:
    ```bash
    brew install python@3.11
    ```

2. Create and activate a virtual environment:
    ```bash
    python3.11 -m venv unravel
    source unravel/bin/activate  # Edit path if needed. To deactivate, run: deactivate
    ```
:::

:::{admonition} Easier virtual environment activation with venv
:class: hint dropdown

#### **Automatically Activate or Create an Alias for Your Virtual Environment**

You can either set your virtual environment to activate automatically when opening a terminal, or create an alias for easier activation.

1. Open your `.bashrc` or `.zshrc` file with a code editor:
    - Using **[nano](https://www.youtube.com/watch?v=DLeATFgGM-A)**:
    ```bash
    nano ~/.bashrc  # or ~/.zshrc for zsh
    ```
    - Using **[VS Code](https://code.visualstudio.com/download)**:
    ```bash
    code ~/.bashrc  # or ~/.zshrc for zsh
    ```

2. **For automatic activation**, add the following line to the end of the file:
    ```bash
    source unravel/bin/activate   # Edit path if needed
    ```

    **Or, to create an alias**, add this line instead:
    ```bash
    alias unravel="source unravel/bin/activate"  # Edit path if needed
    ```

3. Save and apply the changes:
    - If using `nano`, press `Ctrl+X` to exit and follow the prompts.
    - Apply changes by running:
    ```bash
    source ~/.bashrc  # or ~/.zshrc for zsh
    ```

Now, either your virtual environment will automatically activate when you open a terminal, or you can activate it using the `unravel` command.
:::


3. **Install UNRAVEL**

    - With your virtual environment active, follow these steps to install UNRAVEL

    ### Option A: Editable installation of UNRAVEL (recommended)
    * This is allows for editing source code and incremental updates.

    ```bash
    cd <path>  # Insert path to where you want to clone the GitHub repository

    git clone https://github.com/b-heifets/UNRAVEL.git  # Code from the main branch is downloaded

    cd UNRAVEL

    pip install -e .  # This installs python dependencies and sets up commands (both defined in pyproject.toml)
    ```

    ### Option B: Install UNRAVEL via PyPI and use it as-is

    ```bash
    pip install heifetslab-unravel
    ```

4. **Download atlas/template files:**
    - [Google Drive Link](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)
    - We use a 30 µm version of the mouse Allen brain atlas (CCFv3 with 2020 region labels): `atlas_CCFv3_2020_30um.nii.gz`
    - The left hemisphere region labels/IDs are increased by 20,000 in this version: `atlas_CCFv3_2020_30um_split.nii.gz`
    - For registeration with iDISCO/LSFM data, use this `iDISCO_template_CCFv3_30um.nii.gz` (we warped the Gubra atlas to CCFv3 space and refined alignment)
    - For registeration with serial 2P data, use: `average_template_CCFv3_30um.nii.gz`
    - This binary brain mask can be used for 3D brain models: `mask_CCFv3_2020_30um.nii.gz`
    - Use a template that matches your tissue, along with a mask that includes only regions of interest.

5. **Install Ilastik:**
    - [Ilastik installation website](https://www.ilastik.org/download.html).
    - This is used for making a brain mask and segmenting features of interest (e.g., c-Fos+ cells)

6. **Install FSL:**
    - Follow the installation instructions from the [FSL website](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation).
    - FSL includes FSLeyes, which is useful for visualizing data in atlas space and with colored wireframe atlas. 
    - Some scripts depend on FSL.
    - FSL has several command line tools (e.g., fslmaths, fslstats, fslroi, fslcpgeom) that are useful for working with .nii.gz images. 
    - Check that commands work after setting up .bashrc (step 9)
    ```bash
    fslmaths -h  # This should print the help for fslmaths after .bashrc is set up (see below)
    ```
    - Check if the GUIs work
    ```bash
    fsleyes  # This .nii.gz image viewer is useful for checking registration and p value maps
    fsl  # This is used for making files for voxel-wise ANOVAs
    ```
    - If FSL's GUI's don't work, [ITK-SNAP](http://www.itksnap.org/pmwiki/pmwiki.php?n=Main.HomePage) can be used. Contact us for info, a look-up table for atlas coloring, and a wireframe atlas. 

7. **Optional: Install 3D Slicer**
    - [3D Slicer installation](https://download.slicer.org/)
    - This is useful for improving registration by making the autofluo tissue better match the average template (e.g., digitally trimming or adding tissue)

8. **Confirm that the installation worked**
    ```bash
    unravel_commands -c 
    ```

9. **Edit .bashrc or .zshrc to set up dependencies**

    - Add the following to your `.bashrc` or `.zshrc` shell configuration file, and change `/usr/local/` to the path where FSL and Ilastik are installed:

    ```bash
    FSLDIR=/usr/local/fsl  # Update the path to fsl
    . ${FSLDIR}/etc/fslconf/fsl.sh
    PATH=${FSLDIR}/bin:${PATH}
    export FSLDIR PATH
    
    export PATH=/usr/local/ilastik-1.4.0.post1-Linux:$PATH  # Update the path and version
    ```

    - Apply the changes by restarting the terminal or source your shell configuration file: 
    ```bash
    . ~/.bashrc
    ```

10. **Update scripts periodically:**
    :::{hint}
    Note the release/version and/or backup code before updating for reproducibility
    :::

    ### Option A. Updating UNRAVEL if installed via GitHub:
    ```bash
    cd <path/to/UNRAVEL>
    git pull  # This will update the local repo, pulling the latest code from the main branch
    pip install -e .  # This will update commands and install new dependencies
    ```

    ### Option B. Updating UNRAVEL if installed via PyPI:
    ```bash
    pip install --upgrade heifetslab-unravel

    # Check the installed version of UNRAVEL
    pip show heifetslab-unravel
    ```
    To check the latest version, go to the [heifetslab-unravel PyPI page](https://pypi.org/project/heifetslab-unravel/)

--- 

## Checking UNRAVEL Version Changes
* Releases and update notes for UNRAVEL can be found [here](https://github.com/b-heifets/UNRAVEL/releases) on GitHub.
* For more detailed information, you can view the commit history:
    * [Main branch commits](https://github.com/b-heifets/UNRAVEL/commits/main)
    * [Dev branch commits](https://github.com/b-heifets/UNRAVEL/commits/dev)

---

## Viewing Images:
* For full-resolution LSFM images, use [Fiji](https://imagej.net/software/fiji/downloads) or [napari](https://napari.org/stable/).
* NIfTI images (.nii.gz) are commonly used in neuroimaging analysis.
    * They compress well when the images are ~small or if there are many voxels with an intensity of zero. 
    * They can be viewed with [Fiji](https://imagej.net/software/fiji/downloads), [napari](https://napari.org/stable/), or neuroimaging viewers (e.g., [FSLeyes](https://fsl.fmrib.ox.ac.uk/fsl/docs/#/utilities/fsleyes) or [3D Slicer](https://www.slicer.org/)).
    * Fiji needs the [nifti_io plugin](https://imagej.net/ij/plugins/nifti.html)
    * Napari needs the [napari-nifti plugin](https://www.napari-hub.org/plugins/napari-nifti)
    * [FSLeyes](https://fsl.fmrib.ox.ac.uk/fsl/docs/#/utilities/fsleyes) is great for viewing the atlas_CCFv3_2020_30um.nii.gz and matching images; however, it does not work for the 10 µm atlas and larger images.
    * For larger .nii.gz images, use [3D Slicer](https://www.slicer.org/), [ITK-SNAP](http://www.itksnap.org/pmwiki/pmwiki.php), [Fiji](https://imagej.net/software/fiji/downloads), or [napari](https://napari.org/stable/)
* .zarr images are useful for fast compression of large images with lots of non-zero voxels (e.g., raw LSFM data)
    * Use [napari](https://napari.org/stable/) to view them. 

---

## Get Started With Analysis 

[UNRAVEL guide](https://b-heifets.github.io/UNRAVEL/guide.html)