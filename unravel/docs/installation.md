# Installation

* Please send questions/issues to [danrijs@stanford.edu](mailto:danrijs@stanford.edu), so we can improve this guide for future users.

* If you are unfamiliar with the terminal, please review the beginning of our [guide](https://b-heifets.github.io/UNRAVEL/guide.html)


## TL;DR
* Activate a virtual environment in Python
* Install UNRAVEL via [PyPI](https://pypi.org/project/heifetslab-unravel/):
```bash
pip install heifetslab-unravel
```
* Or, for an editable install run:
```bash
git clone https://github.com/b-heifets/UNRAVEL.git
cd UNRAVEL
pip install -e .  # Also run this for updates
```
* Download atlas/template files: [Google Drive Link](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)
* Install [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation)
* Install [Ilastik](https://www.ilastik.org/download.html)



## Updating UNRAVEL

To update UNRAVEL to the latest version, use the following command:

```bash
pip install --upgrade heifetslab-unravel
```

:::{admonition} Please note the version of UNRAVEL you are using for reproducibility.
:class: note dropdown

To check the installed version of UNRAVEL, use the following command:

```bash
pip show heifetslab-unravel

```

To check the latest version, go to the [heifetslab-unravel PyPI page](https://pypi.org/project/heifetslab-unravel/)
:::

:::{admonition} Checking changes between versions
:class: note dropdown

Releases and update notes for UNRAVEL can be found [here](https://github.com/b-heifets/UNRAVEL/releases) on GitHub .

For more detailed information, you can view the commit history:
* [Main branch commits](https://github.com/b-heifets/UNRAVEL/commits/main)
* [Dev branch commits](https://github.com/b-heifets/UNRAVEL/commits/dev)
:::


## Setting Up Windows Subsystem for Linux (WSL)

If you are using Windows and are unfamilar with WSL, check out the first few min of this [video](https://www.youtube.com/watch?v=-atblwgc63E) 

### Installing WSL:
- Open the start menu, search for PowerShell, and right click on PowerShell to run it as an Administrator. Then run:
    ```powershell
    wsl --install

    # If that does not work, run this
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
    python3.11 -m venv unravel_env
    source unravel_env/bin/activate
    ```


3. **Install UNRAVEL:**
    ```bash
    pip install heifetslab-unravel
    ```

4. **Download atlas/template files:**
    [Google Drive Link](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)

:::{todo}
* Update the paths to atlas files so they work with paths relative to the project
:::

5. **Install Ilastik:**
    - [Ilastik installation website](https://www.ilastik.org/download.html).

6. **Install FSL:**
    - Follow the installation instructions from the [FSL website](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation).
    - Example for Ubuntu:
        ```bash
        sudo apt-get update
        sudo apt-get install -y fsl
        ```

7. **Confirm the installation**
    ```bash
    unravel_commands -c 
    ```

## Edit .bashrc or .zshrc to set up dependencies

Add the following to your `.bashrc` or `.zshrc` shell configuration file, and change `/usr/local/` to the path where FSL and Ilastik are installed:

```bash
export PATH=$PATH:/usr/local/fsl/bin
export FSLDIR=/usr/local/fsl
PATH=${FSLDIR}/bin:${PATH}
. ${FSLDIR}/etc/fslconf/fsl.sh
export FSLDIR PATH
export PATH=/usr/local/ilastik-1.3.3post3-Linux:$PATH # Update the version

# Add this too if you want to open ilastik via the terminal by running: ilastik
alias ilastik=run_ilastik.sh
```

Apply the changes by restarting the terminal or source your shell configuration file: 
```bash
. ~/.bashrc
```


## Get started with analysis 

[UNRAVEL guide](https://b-heifets.github.io/UNRAVEL/guide.html)


## Optional: editable installation of UNRAVEL

* This is an alternate installation method from `pip install heifetslab-unravel`

1. **Open a terminal and navigate to the directory where you want to clone the UNRAVEL GitHub repository:**

2. **Clone the repository:**
    ```bash
    git clone https://github.com/b-heifets/UNRAVEL.git
    ```
    [GitHub Cloning Documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository)

3. **Install UNRAVEL locally**
    ```bash
    cd UNRAVEL
    <activate a virtual environment> # e.g., pyenv activate unravel
    pip install -e .
    ```

4. **Update scripts periodically:**
    :::{hint}
    * Make a backup of the code that you used for analysis before updating
    :::

    ```bash
    cd <path/to/UNRAVEL>
    git pull  # This will update the local repo
    pip install -e .  # This will update commands and install new dependencies
    ```

:::{note}
To add extra depedencies (e.g., for updating documentation), run: ``pip install -e ".[dev]"``
:::