#!/usr/bin/env python3

"""
Utility functions and decorators for handling configurations, processing files and directories,
and enhancing command-line scripts with progress bars and detailed function execution info.

Classes:
    - CustomMofNCompleteColumn: Progress bar column for completed/total items.
    - CustomTimeElapsedColumn: Progress bar column for elapsed time in green.
    - CustomTimeRemainingColumn: Progress bar column for remaining time in dark orange.
    - AverageTimePerIterationColumn: Progress bar column for average time per iteration.

Functions:
    - load_config: Load settings from a config file.
    - get_samples: Get a list of sample directories based on provided parameters.
    - initialize_progress_bar: Initialize a Rich progress bar.
    - verbose_start_msg: Print the start command and time if verbose mode is enabled.
    - verbose_end_msg: Print the end time if verbose mode is enabled.
    - log_command: Decorator to log the command and execution times to a hidden file.
    - print_func_name_args_times: Decorator to print function execution details.
    - load_text_from_file: Load text content from a file.
    - copy_files: Copy specified files from source to target directory.

Usage:
    Import the functions and decorators to enhance your scripts.

Examples:
    - from unravel.core.utils import load_config, get_samples, initialize_progress_bar, print_func_name_args_times, load_text_from_file copy_files
    - config = load_config("path/to/config.ini")
    - samples = get_samples(exp_dir_paths=["/path/to/exp1", "/path/to/exp2"])
    - progress, task_id = initialize_progress_bar(len(samples), task_message="[red]Processing samples...")

"""

import argparse
import functools
import shutil
import numpy as np
import os
import sys
import threading
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from rich import print
from rich.console import Console
from rich.progress import Progress, TextColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn, ProgressColumn
from rich.text import Text

from unravel.core.config import Configuration, Config

# Configuration loading
def load_config(config_path):
    """Load settings from the config file and return a Config object."""
    if Path(config_path).exists():
        cfg = Config(config_path)
    else:
        print(f'\n    [red]{config_path} does not exist\n')
        import sys ; sys.exit()
    return cfg

# Sample list 
def get_samples(sample_dir_list=None, sample_dir_pattern="sample??", exp_dir_paths=None):
    """
    Return a list of full paths to sample directories (dirs) based on the dir list, pattern, and/or experiment dirs.

    This function searches for dirs matching a specific pattern (default "sample??") within the given experiment dirs.
    If a sample_dir_list is provided, it uses the full paths from the list or resolves them if necessary.
    If an exp_dir_paths list is provided, it searches for sample dirs within each experiment directory.
    If both sample_dir_list and exp_dir_paths are provided, paths are added to the list from both sources.    

    Parameters:
    - sample_dir_list (list of str or None): Explicit list of dirs to include. Can be dir names or absolute paths.
    - sample_dir_pattern (str): Pattern to match dirs within experiment dirs. Defaults to "sample??".
    - exp_dir_paths (list of str or None): List of paths to experiment dirs where subdirs matching the sample_dir_pattern will be searched for.

    Returns:
    - list of pathlib.Path: Full paths to all found sample dirs.
    """
    samples = []

    # Ensure sample_dir_list is a list
    if isinstance(sample_dir_list, str):
        sample_dir_list = [sample_dir_list]  # Convert string to list

    # Add full paths of dirs from sample_dir_list that exist
    if sample_dir_list:
        for dir_name in sample_dir_list:
            dir_path = Path(dir_name)
            dir_path = dir_path if dir_path.is_absolute() else dir_path.resolve()
            if dir_path.is_dir():
                samples.append(dir_path)

    # Search for sample folders within each experiment directory in exp_dir_paths and add their full paths
    if exp_dir_paths:
        for exp_dir in exp_dir_paths:
            exp_path = Path(exp_dir).resolve()
            if exp_path.is_dir():
                found_samples = [
                    d.resolve() for d in exp_path.iterdir()
                    if d.is_dir() and fnmatch(d.name, sample_dir_pattern)
                ]
                samples.extend(found_samples)

    # If no dirs have been added yet, search the current working directory for dirs matching the pattern
    if not samples:
        cwd_samples = [
            d.resolve() for d in Path.cwd().iterdir()
            if d.is_dir() and fnmatch(d.name, sample_dir_pattern)
        ]
        samples.extend(cwd_samples)

    # Use the current working directory as the fallback if no samples found
    if not samples:
        samples.append(Path.cwd())

    return samples


# Progress bar functions
class CustomMofNCompleteColumn(MofNCompleteColumn):
    def render(self, task) -> Text:
        completed = str(task.completed)
        total = str(task.total)
        return Text(f"{completed}/{total}", style="bright_cyan") 

class CustomTimeElapsedColumn(TimeElapsedColumn):
    def render(self, task) -> Text:
        time_elapsed = super().render(task)
        time_elapsed.stylize("green")
        return time_elapsed
    
class CustomTimeRemainingColumn(TimeRemainingColumn):
    def render(self, task) -> Text:
        time_elapsed = super().render(task)
        time_elapsed.stylize("dark_orange")
        return time_elapsed

class AverageTimePerIterationColumn(ProgressColumn):
    def render(self, task) -> Text:
        """
        Render the average time per iteration.

        Args:
            task: An object representing a task, which should have a `speed` attribute.

        Returns:
            A Text object displaying the average time per iteration.
        """
        speed = task.speed or 0
        if speed > 0:
            avg_time = f"{1 / speed:.2f}s/iter"
        else:
            avg_time = "."
        return Text(avg_time, style="red1")

def initialize_progress_bar(num_of_items_to_iterate, task_message="[red]Processing..."):
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        SpinnerColumn(style="bright_magenta"),
        BarColumn(complete_style="purple3", finished_style="purple"),
        TextColumn("[bright_blue]{task.percentage:>3.0f}%[progress.percentage]"),
        CustomMofNCompleteColumn(),
        CustomTimeElapsedColumn(),
        TextColumn("[gold1]eta:"),
        CustomTimeRemainingColumn(),
        AverageTimePerIterationColumn()
    )
    task_id = progress.add_task(task_message, total=num_of_items_to_iterate)
    return progress, task_id


# Logging and printing functions
console = Console()

def verbose_start_msg():
    """Print the start command and time if verbose mode is enabled."""
    if Configuration.verbose:
        cmd = f"\n{os.path.basename(sys.argv[0])} {' '.join(sys.argv[1:])}"
        console.print(f"\n\n[bold bright_magenta]{os.path.basename(sys.argv[0])}[/] [purple3]{' '.join(sys.argv[1:])}[/]\n")
        print(f"\n    [bright_blue]Start:[/] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        return cmd
    return None

def verbose_end_msg():
    """Print the end time if verbose mode is enabled."""
    if Configuration.verbose:
        end_time = datetime.now()
        console.print(f"\n\n:mushroom: [bold bright_magenta]{os.path.basename(sys.argv[0])}[/] [purple3]finished[/] [bright_blue]at:[/] {end_time.strftime('%Y-%m-%d %H:%M:%S')}[gold1]![/][dark_orange]![/][red1]![/] \n")
        return end_time.strftime('%Y-%m-%d %H:%M:%S')
    return None

def log_command(func):
    """A decorator for main() to log the command and execution times to a hidden file (.command_log.txt)."""
    # TODO: avoid logging when -h or --help is used
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        log_file = ".command_log.txt"  # Name of the hidden log file

        # Command string
        cmd = f"\n{os.path.basename(sys.argv[0])} {' '.join(sys.argv[1:])}"

        # Log command to file
        with open(log_file, "a") as file:  # Open in append mode
            file.write(cmd)
            start_time = datetime.now()
            file.write(f"\n    Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        result = func(*args, **kwargs)  # Call the original function

        # Always log end time to file
        with open(log_file, "a") as file:
            end_time = datetime.now()
            file.write(f"\n    End: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        return result
    return wrapper


# Function decorator

def get_dir_name_from_args(args, kwargs):
    """
    This function checks args and kwargs for a file or directory path
    and returns a string based on the name of the file or directory.
    """
    for arg in args:
        if isinstance(arg, (str, Path)) and Path(arg).exists():
            return Path(arg).resolve().name

    for kwarg in kwargs.values():
        if isinstance(kwarg, (str, Path)) and Path(kwarg).exists():
            return Path(kwarg).resolve().name

    return Path.cwd().name

# Create a thread-local storage for indentation level
thread_local_data = threading.local()
thread_local_data.indentation_level = 0

def print_func_name_args_times(print_dir=True):
    """A decorator that prints the function name, arguments, duration, and memory usage of the function it decorates."""
    
    ARG_REPRESENTATIONS = {
        np.ndarray: lambda x: f"ndarray: {x.shape} {x.dtype}",
        list: lambda x: f"list: {x[:5]}{'...' if len(x) > 5 else ''}",
        str: str,
        int: str,
        float: str,
        Path: str
    }

    def arg_str_representation(arg):
        """Return a string representation of the argument passed to the decorated function."""
        # return ARG_REPRESENTATIONS.get(type(arg), str)(arg)
        return ARG_REPRESENTATIONS.get(type(arg), repr)(arg)
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper_timer(*args, **kwargs):
            if not Configuration.verbose:
                return func(*args, **kwargs)  # If not verbose, skip all additional logic
            
            func_args_str = ', '.join(repr(arg) for arg in args) 
            func_kwargs_str = ', '.join(f"{k}={v!r}" for k, v in kwargs.items())
            combined_args = func_args_str + (', ' if func_args_str and func_kwargs_str else '') + func_kwargs_str
            
            # Increment the indentation level
            if not hasattr(thread_local_data, 'indentation_level'):
                thread_local_data.indentation_level = 0
            thread_local_data.indentation_level += 1

            # Compute indentation based on the current level
            indent_str = '  ' * thread_local_data.indentation_level  # Using 4 spaces for each indentation level
            
            # Convert args and kwargs to string for printing
            args_str = ', '.join(arg_str_representation(arg) for arg in args)
            kwargs_str = ', '.join(f"{k}={arg_str_representation(v)}" for k, v in kwargs.items())
            combined_args = args_str + (', ' if args_str and kwargs_str else '') + kwargs_str
            
            if print_dir:
                dir_name = get_dir_name_from_args(args, kwargs) # Get dir name the basename of 1st arg with a valid path (e.g., sample??)
                dir_string = f" for [bold orange_red1]{dir_name}[/]"
            else:
                dir_string = ""

            # Print out the arguments with the added indent
            if thread_local_data.indentation_level > 2:  # considering that main function is at level 1
                print(f"{indent_str}[gold3]{func.__name__!r}[/]\n{indent_str}[bright_black]({args_str}{', ' + kwargs_str if kwargs_str else ''})")
            elif thread_local_data.indentation_level > 1:
                print(f"\n{indent_str}[gold3]{func.__name__!r}[/]\n{indent_str}[bright_black]({args_str}{', ' + kwargs_str if kwargs_str else ''})")
            else:
                print(f"\nRunning: [bold gold1]{func.__name__!r}[/]{dir_string} with args: [bright_black]({combined_args})[/]")

            # Function execution
            start_time = time.perf_counter()
            result = func(*args, **kwargs) # Call the actual function
            end_time = time.perf_counter()

            # Print duration
            run_time = end_time - start_time
            minutes, seconds = divmod(run_time, 60)
            duration_str = f"{minutes:.0f} min {seconds:.4f} sec" if minutes else f"{seconds:.4f} sec"

            # Print out the arguments with the added indent
            if thread_local_data.indentation_level > 1:  # considering that main function is at level 1
                print(f"{indent_str}[gold3]{duration_str}")
            else:
                print(f"\nFinished [bold gold1]{func.__name__!r}[/] in [orange_red1]{duration_str}\n")

            thread_local_data.indentation_level -= 1
            return result
        return wrapper_timer
    return decorator

@print_func_name_args_times()
def load_text_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        print(f"[red]Error reading file: {e}[/]")
        return None

@print_func_name_args_times()
def copy_files(source_dir, target_dir, filename, sample_path=None, verbose=False):
    """Copy the specified slices to the target directory.
    
    Args:
        - source_dir (Path): Path to the source directory containing the .tif files.
        - target_dir (Path): Path to the target directory where the selected slices will be copied.
        - filename (str): Name of the file to copy.
        - sample_path (Path): Path to the sample directory (provide to prepend to the filename).
        - verbose (bool): Increase verbosity."""
    
    src_file = Path(source_dir, filename)
    
    if src_file.exists():
        if sample_path is not None:
            dest_file = target_dir / f'{sample_path.name}_{filename}'
        else: 
            dest_file = target_dir / filename
        shutil.copy(src_file, dest_file)
        if verbose:
            print(f"Copied {src_file} to {dest_file}")
    else:
        if verbose:
            print(f"File {src_file} does not exist and was not copied.")