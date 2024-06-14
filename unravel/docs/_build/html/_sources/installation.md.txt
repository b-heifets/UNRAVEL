# Installation

Please send questions/issues to [danrijs@stanford.edu](mailto:danrijs@stanford.edu), so we can improve this guide for future users.

## Setting Up Windows Subsystem for Linux (WSL)

1. **Install WSL:**

    - Open PowerShell as Administrator and run:
      ```powershell
      wsl --install
      ```

    - Restart your computer if prompted.

2. **Install a Linux distribution:**

    - After the restart, open the Microsoft Store and install your preferred Linux distribution (e.g., Ubuntu).

3. **Initialize your Linux distribution:**

    - Open your installed Linux distribution from the Start menu.
    - Follow the prompts to set up your username and password.

For detailed instructions, visit the [WSL Installation Guide](https://docs.microsoft.com/en-us/windows/wsl/install).

## Installing UNRAVEL on Linux or WSL

1. **Open a terminal and navigate to the directory where you want to clone the UNRAVEL GitHub repository:**

2. **Clone the repository:**
    ```bash
    git clone https://github.com/b-heifets/UNRAVEL.git
    git checkout dev
    ```
    [GitHub Cloning Documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository)

3. **Install pyenv to manage Python versions and create a virtual environment:**

    **a. Install dependencies:**
    ```bash
    sudo apt-get update
    sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev \
    libffi-dev liblzma-dev python-openssl git
    ```

    **b. Install pyenv:**
    ```bash
    curl https://pyenv.run | bash
    ```

    **c. Add pyenv to your shell startup file (.bashrc or .zshrx):**
    ```bash
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init --path)"\nfi' >> ~/.bashrc
    echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi' >> ~/.bashrc
    exec "$SHELL"
    ```

    [pyenv Installation Guide](https://github.com/pyenv/pyenv#installation)

4. **Install Python 3.11:**
    ```bash
    pyenv install 3.11.3
    ```

5. **Create and activate a virtual environment:**
    ```bash
    pyenv virtualenv 3.11.3 unravel
    pyenv activate unravel
    ```

6. **Install pip if needed:**
    [Pip Installation Guide](https://pip.pypa.io/en/stable/installation/)

7. **Install UNRAVEL locally:**
    ```bash
    pip install -e .
    ```

:::{todo}
Add unravel to PyPI so that users can install it by running something like: 

```bash
pip install unravel
```
:::


8. **Download atlas/template files and locate them in `./atlas/`:**
    [Google Drive Link](https://drive.google.com/drive/folders/1iZjQlPc2kPagnVsjWEFFObLlkSc2yRf9?usp=sharing)

9. **Install Ilastik:**
    - Download the Ilastik installer from the [Ilastik website](https://www.ilastik.org/download.html).
    - Follow the installation instructions specific to your operating system.
    - Example for Linux:
        ```bash
        wget https://files.ilastik.org/ilastik-1.3.3post3-Linux.tar.bz2
        tar -xjf ilastik-1.3.3post3-Linux.tar.bz2
        sudo mv ilastik-1.3.3post3-Linux /usr/local/
        ```

10. **Install FSL:**
    - Follow the installation instructions from the [FSL website](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation).
    - Example for Ubuntu:
        ```bash
        sudo apt-get update
        sudo apt-get install -y fsl
        ```

11. **Confirm the installation and get started by viewing the help guide in `prep_reg.py`:**
    ```bash
    prep_reg.py -h
    ```

12. **Update scripts periodically:**
    ```bash
    git pull
    ```

## Editing .bashrc or .zshrc

Add the following to your `.bashrc` or `.zshrc` file, and change `/usr/local/` to the path where FSL is installed:

```bash
export PATH=$PATH:/usr/local/fsl/bin
export FSLDIR=/usr/local/fsl
PATH=${FSLDIR}/bin:${PATH}
. ${FSLDIR}/etc/fslconf/fsl.sh
export FSLDIR PATH
export PATH=/usr/local/ilastik-1.3.3post3-Linux:$PATH
