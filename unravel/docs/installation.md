# Installation

* Please send questions/issues to [danrijs@stanford.edu](mailto:danrijs@stanford.edu), so we can improve this guide for future users.

* If you are unfamiliar with the terminal, please review the beginning of our [guide](https://b-heifets.github.io/UNRAVEL/guide.html)


## TL;DR
* Activate a virtual environment in Python
* **Option A:** install UNRAVEL via GitHub (for editing source code and/or incremental updates):
```bash
# Install latest code on the main branch
git clone https://github.com/b-heifets/UNRAVEL.git
cd UNRAVEL
pip install -e .

# Update
git pull 
pip install -e . 
```
* **Option B:** install UNRAVEL via [PyPI](https://pypi.org/project/heifetslab-unravel/):
```bash
# Install latest release
pip install heifetslab-unravel

# Update
pip install --upgrade heifetslab-unravel
```
* Confirm that the installation worked: 
```bash
unravel_commands -c  # or: uc -c
```
* **[Download atlas/template files](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)**
    * This has an [iDISCO/LSFM-specific template](https://pubmed.ncbi.nlm.nih.gov/33063286/) that we warped to 30 µm CCFv3 space
* **Required software:**
    * [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation) for voxel-wise stats and CLI tools
    * [Ilastik](https://www.ilastik.org/download.html) for segmenting features of interest
* **Recommended software:**
    * [3D Slicer](https://download.slicer.org/) for 3D painting to make brains more like the average template (improves registration)
    * [DSI Studio](https://dsi-studio.labsolver.org/download.html) for 3D brain models
    * [Flourish](https://app.flourish.studio/login) for sunburst plots (free web app)


## Setting Up Windows Subsystem for Linux (WSL)

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
:::


## Installing UNRAVEL on Linux or WSL

1. **Open a terminal**

2. **Install [pyenv](https://github.com/pyenv/pyenv), [venv](https://docs.python.org/3/library/venv.html), [conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html), or other tool(s) to manage Python versions and create a virtual environment:**

    ### Option A: Using pyenv

    :::{note}
    "pyenv lets you easily switch between multiple versions of Python."
    It works on Linux, macOS, and WSL. 
    For Windows, use [pyenv-win](https://github.com/pyenv-win/pyenv-win) ([more info](https://github.com/pyenv/pyenv))
    :::

    **a. Install python build dependencies:**

    - **For Linux and WSL:**
    ```bash
    sudo apt update
    
    sudo apt install build-essential libssl-dev zlib1g-dev \ 
    libbz2-dev libreadline-dev libsqlite3-dev curl git \ 
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
    ```
    - **For macOS:**
    ```bash
    xcode-select --install  # If not available, see: https://github.com/pyenv/pyenv/wiki#suggested-build-environment

    # Install Homebrew if not yet installed (https://brew.sh/)
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    brew install openssl readline sqlite3 xz zlib tcl-tk
    brew update  
    ```

    **b. Install [pyenv](https://github.com/pyenv/pyenv#installation):**
    ```bash
    # Linux or WSL:
    curl https://pyenv.run | bash

    # macOS:
    brew install pyenv
    ```

    **c. Set up pyenv in your shell startup file (.bashrc or .zshrc):**
    ```bash
    (
    # Run these commands to add lines to ~/.bashrc
    echo '' >> ~/.bashrc
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
    echo '' >> ~/.bashrc
    . ~/.bashrc  # Source .bashrc for changes to take effect
    )

    (
    # Or for zsh run these commands to add lines to ~/.zshrc
    echo '' >> ~/.zshrc
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
    echo 'eval "$(pyenv init -)"' >> ~/.zshrc
    echo '' >> ~/.zshrc
    . ~/.zshrc  # Source .zshrc for changes to take effect
    )

    ```

    **d. Install Python 3.11:**
    ```bash
    pyenv install 3.11.3
    ```

    **e. Create and activate a virtual environment:**
    ```bash
    pyenv virtualenv 3.11.3 unravel
    pyenv activate unravel  # To deactivate, run: pyenv deactivate
    ```

    ### Option B: Using venv

    **a. Install Python 3.11 if it's not already installed:**
    - **For Linux and WSL:**
    ```bash
    sudo apt-get update
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
    ```
    - **For macOS:**
    ```bash
    brew install python@3.11
    ```

    **b. Create and activate a virtual environment:**
    ```bash
    python3.11 -m venv unravel
    source unravel/bin/activate
    ```


3. **Install UNRAVEL**

    ### Option A: Install UNRAVEL via PyPI and use as-is

    ```bash
    pip install heifetslab-unravel
    ```

    ### Option B: Editable installation of UNRAVEL

    ```bash
    cd <path>  # Insert path to where you want to clone the GitHub repository

    git clone https://github.com/b-heifets/UNRAVEL.git  # Clone the repo

    cd UNRAVEL

    <command to activate a virtual environment> # e.g., pyenv activate unravel

    pip install -e .
    ```

    :::{note}
    If you want to use another branch, run the following before ``pip install -e .``: 
    git checkout <branch-name>  # Check out the desired remote branch (e.g., dev)

    To add extra depedencies (e.g., for updating documentation), run: ``pip install -e ".[dev]"`
    :::

4. **Download atlas/template files:**
    [Google Drive Link](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)

5. **Install Ilastik:**
    - [Ilastik installation website](https://www.ilastik.org/download.html).
    - This is used for making a brain mask and segmenting features of interest (e.g., c-Fos+ cells)

6. **Install FSL:**
    - Follow the installation instructions from the [FSL website](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation).
    - Example for Ubuntu:
        ```bash
        sudo apt-get update
        sudo apt-get install -y fsl
        ```
    - This installation includes FSLeyes, which is useful for visualizing data in atlas space and with colored wireframe atlas. 
    - Some scripts depend on FSL.
    - FSL has several command line tools (e.g., fslmaths, fslstats, fslroi, fslcpgeom) that are useful for working with .nii.gz images. 

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
    export PATH=$PATH:/usr/local/fsl/bin
    export FSLDIR=/usr/local/fsl
    PATH=${FSLDIR}/bin:${PATH}
    . ${FSLDIR}/etc/fslconf/fsl.sh
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

    ### Option A. Updating UNRAVEL if installed via PyPI:
    ```bash
    # Update UNRAVEL if installed via PyPI: 
    pip install --upgrade heifetslab-unravel

    # Check the installed version of UNRAVEL
    pip show heifetslab-unravel
    ```
    To check the latest version, go to the [heifetslab-unravel PyPI page](https://pypi.org/project/heifetslab-unravel/)

    ### Option B. Updating UNRAVEL if installed via GitHub:
    This is allows for editing source code and incremental updates
    ```bash
    cd <path/to/UNRAVEL>
    git pull  # This will update the local repo
    pip install -e .  # This will update commands and install new dependencies
    ```

:::{admonition} Checking changes between versions
:class: note dropdown

Releases and update notes for UNRAVEL can be found [here](https://github.com/b-heifets/UNRAVEL/releases) on GitHub .

For more detailed information, you can view the commit history:
* [Main branch commits](https://github.com/b-heifets/UNRAVEL/commits/main)
* [Dev branch commits](https://github.com/b-heifets/UNRAVEL/commits/dev)
:::

## Viewing images:

* .nii.gz images are commonly created during analysis. 
* They compress well when small or if there are many voxels with an intensity of zero. 
* They can be viewed with [Fiji](https://imagej.net/software/fiji/downloads), [napari](https://napari.org/stable/), or neuroimaging viewers (e.g., FSLeyes)
* Fiji needs the [nifti_io plugin](https://imagej.net/ij/plugins/nifti.html)
* Napari needs the [napari-nifti plugin](https://www.napari-hub.org/plugins/napari-nifti)


## Get started with analysis 

[UNRAVEL guide](https://b-heifets.github.io/UNRAVEL/guide.html)