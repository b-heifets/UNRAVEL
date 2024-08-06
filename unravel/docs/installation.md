# Installation

* Please send questions/issues to [danrijs@stanford.edu](mailto:danrijs@stanford.edu), so we can improve this guide for future users.

* If you are unfamiliar with the terminal, please review the beginning of our [guide](https://b-heifets.github.io/UNRAVEL/guide.html)


## TL;DR
* Activate a virtual environment in Python
* **Option A:** install UNRAVEL via [PyPI](https://pypi.org/project/heifetslab-unravel/):
```bash
# Install latest release
pip install heifetslab-unravel

# Update
pip install --upgrade heifetslab-unravel
```
* **Option B:** install UNRAVEL via GitHub (for editing source code and/or incremental updates):
```bash
# Install latest code on the main branch
git clone https://github.com/b-heifets/UNRAVEL.git
cd UNRAVEL
pip install -e .

# Update
git pull 
pip install -e . 
```
* Confirm that the installation worked: 
```bash
unravel_commands -c  # This should print common commands
```
* Download atlas/template files: [Google Drive Link](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)
* Install [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation)
* Install [Ilastik](https://www.ilastik.org/download.html)


## Setting Up Windows Subsystem for Linux (WSL)

If you are using Windows and are unfamilar with WSL, check out the first few min of this [video](https://www.youtube.com/watch?v=-atblwgc63E) 

### Installing WSL:
- Open the start menu, search for PowerShell, and right click on PowerShell to run it as an Administrator. Then run:
    ```powershell
    wsl --install  # If this works, the Ubuntu linux distrobution will be installed by default

    # If that does not work, run this and follow additional steps
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
    ```
- Restart your computer when prompted.
- Open the Microsoft Store and search "linux" --> Run Linux On Windows
- Select Ubuntu and install
- Open the PowerShell and start WSL by running: 
    ```powershell
    wsl
    ```
- Or open the WSL app or the Ubuntu app from that Start menu.
- Follow the prompts to set up your username and password.

For detailed installation instructions, visit the [WSL Installation Guide](https://learn.microsoft.com/en-us/windows/wsl/install).

:::{note}
To enable copy/paste in the PowerShell or WSL, click the icon in the upper left --> Properties --> Edit Options -> check "Use Ctrl+Shift+C/V as Copy/Paste --> OK. 

[Video tutorial](https://www.youtube.com/watch?v=i547sSXhq0E) on navigating to your files (either the WSL file system or your C and D drives).
:::



## Installing UNRAVEL on Linux or WSL

1. **Open a terminal**

2. **Install pyenv, venv, or other tool(s) to manage Python versions and create a virtual environment:**

    ### Option A: Using pyenv

    :::{note}
    Pyenv can work on Windows, but this is not recommended (e.g., see notes [here](https://github.com/pyenv/pyenv))
    
    Alternatively, use [pyenv-win](https://github.com/pyenv-win/pyenv-win), [venv](https://docs.python.org/3/library/venv.html), or [conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).
    :::

    **a. Install dependencies:**
    ```bash
    sudo apt-get update

    sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev \
    libffi-dev liblzma-dev python3-openssl git
    ```

    **b. Install [pyenv](https://github.com/pyenv/pyenv#installation):**
    ```bash
    curl https://pyenv.run | bash
    ```

    **c. Add pyenv to your shell startup file (.bashrc or .zshrc):**
    ```bash
    (
    echo '' >> ~/.bashrc
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
    echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
    )
    ```

    **d. Install Python 3.11:**
    ```bash
    pyenv install 3.11.3
    ```

    **e. Create and activate a virtual environment:**
    ```bash
    pyenv virtualenv 3.11.3 unravel
    pyenv activate unravel # To deactivate, run: pyenv deactivate
    ```

    ### Option B: Using venv

    **a. Install Python 3.11 if it's not already installed:**
    ```bash
    sudo apt-get update
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
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

6. **Install FSL:**
    - Follow the installation instructions from the [FSL website](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation).
    - Example for Ubuntu:
        ```bash
        sudo apt-get update
        sudo apt-get install -y fsl
        ```

7. **Confirm that the installation worked**
    ```bash
    unravel_commands -c 
    ```

8. **Edit .bashrc or .zshrc to set up dependencies**

    - Add the following to your `.bashrc` or `.zshrc` shell configuration file, and change `/usr/local/` to the path where FSL and Ilastik are installed:

    ```bash
    export PATH=$PATH:/usr/local/fsl/bin
    export FSLDIR=/usr/local/fsl
    PATH=${FSLDIR}/bin:${PATH}
    . ${FSLDIR}/etc/fslconf/fsl.sh
    export FSLDIR PATH
    export PATH=/usr/local/ilastik-1.3.3post3-Linux:$PATH # Update the path and version
    ```

    - Apply the changes by restarting the terminal or source your shell configuration file: 
    ```bash
    . ~/.bashrc
    ```

9. **Update scripts periodically:**
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



## Get started with analysis 

[UNRAVEL guide](https://b-heifets.github.io/UNRAVEL/guide.html)