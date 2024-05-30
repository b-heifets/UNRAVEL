#!/usr/bin/env python3

from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install
from cfonts import render
import builtins

def print_UNRAVEL():
    """Function to print the UNRAVEL logo."""
    output = render('UNRAVEL', gradient=['red', 'magenta'], align='center')
    builtins.print(output)

class PostDevelopCommand(develop):
    """Post-installation for development mode."""
    def run(self):
        develop.run(self)
        # Print UNRAVEL logo after installation
        print_UNRAVEL()
        # You can also call other post-install scripts here if needed

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        # Print UNRAVEL logo after installation
        print_UNRAVEL()

setup(
    name='unrvl',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'some_dependency',
        'another_dependency',
        'cfonts',  # Ensure that cfonts is a dependency
    ],
    cmdclass={
        'develop': PostDevelopCommand,
        'install': PostInstallCommand,
    },
    entry_points={
        'console_scripts': [
            'unrvl-config=unrvl.configurator:setup_unrvl',
        ],
    },
)

# Daniel Rijsketic 08/30/2023 (Heifets lab)

