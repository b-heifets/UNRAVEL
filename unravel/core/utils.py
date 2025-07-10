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
    - process_files_with_glob: Process files matching a glob pattern using a processing function.

Usage:
    Import the functions and decorators to enhance your scripts.

Examples:
    >>> # Import the functions and decorators
    >>> from unravel.core.utils import load_config, get_samples, initialize_progress_bar, print_func_name_args_times, load_text_from_file, copy_files

    >>> # Load the configuration from a file
    >>> config = load_config("path/to/config.ini")

    >>> # Get a list of sample directories
    >>> samples = get_samples(["path/to/dir1", "path/to/dir2"], dir_pattern="sample??", verbose=True)
    
    >>> # Initialize a progress bar
    >>> progress, task_id = initialize_progress_bar(len(samples), task_message="[red]Processing samples...")

"""

import functools
import shutil
import numpy as np
import os
import sys
import threading
import time
from datetime import datetime
from fnmatch import fnmatch
from glob import glob
from pathlib import Path
from rich import print
from rich.console import Console
from rich.progress import Progress, TextColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn, ProgressColumn
from rich.text import Text

from unravel.core.config import Configuration, Config

# TODO: Also output commands with default args to .verbose_command_log.txt or .command_log.txt. Rename to unravel_command_log.txt
# TODO: Add a function for getting the stem from file names or paths that works with exensions with one or more dots.

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
def get_samples(dir_list=None, dir_pattern="sample??", verbose=False):
    """
    Finds and returns paths to directories matching a specified pattern within given directories 
    or, if none are provided, the current working directory.

    Parameters
    ----------
    dir_list : list of Path or str, or Path or str, optional
        A list of paths (as Path objects or strings) to sample?? directories
        or directories that may contain subdirectories matching the `dir_pattern`. 

    dir_pattern : str, optional
        A pattern to match directory names, default is "sample??", where "?" is a wildcard matching a 
        single character. This pattern is used to identify directories of interest.

    dir_pattern : str, optional
        A Unix shell-style wildcard pattern used by `fnmatch` to match directory names. 
        Default is "sample??", where each "?" matches a single character. 

    verbose : bool, optional
        If True, prints the found directories, grouped by their parent directories.
        Default is False.

    Returns
    -------
    samples : list of Path
        A list of resolved Path objects pointing to directories that match the `dir_pattern`.

    Notes
    -----
    - If no directories are provided via `dir_list`, the function searches the current working directory.
    - If a directory (e.g., the current dir) matches the `dir_pattern`, 
      it is included in the results and not searched for subdirectories.

    Examples
    --------
    >>> sample_paths = get_samples()  # Search the current working directory for sample?? directories
    >>> sample_paths = get_samples([path1, path2], dir_pattern="sample???")  # Search path1 and path2 for sample??? directories
    """
    samples = []

    if isinstance(dir_list, (str, Path)):
        dir_list = [Path(dir_list)]

    if dir_list:
        for dir_name in dir_list:
            dir_path = Path(dir_name).resolve()

            if dir_path.is_dir():
                # Check if the provided path itself matches the pattern
                if fnmatch(dir_path.name, dir_pattern):
                    samples.append(dir_path)
                else:
                    # Search for subdirectories matching the pattern
                    sample_dirs = sorted([d.resolve() for d in dir_path.iterdir() if d.is_dir() and fnmatch(d.name, dir_pattern)])
                    samples.extend(sample_dirs)
            else:
                print(f"\n    [red1]Directory {dir_path} does not exist or is not a directory\n")
    else:
        # If the cwd matches the pattern, add it to the list of samples
        cwd = Path.cwd()
        if fnmatch(cwd.name, dir_pattern):
            samples.append(cwd.resolve())
        else:
            # Search the current working directory for matching dirs
            cwd_samples = sorted([d.resolve() for d in cwd.iterdir() if d.is_dir() and fnmatch(d.name, dir_pattern)])
            samples.extend(cwd_samples)

        # Final fallback to add the CWD if nothing else was found
        if not samples:
            samples.append(cwd.resolve())

    if verbose:
        # Create an ordered list of unique parent directories
        uniq_parent_dirs = []
        for dir_name in dir_list or [Path.cwd()]:
            dir_path = Path(dir_name).resolve()
            parent_dir = dir_path.parent if fnmatch(dir_path.name, dir_pattern) else dir_path
            if parent_dir not in uniq_parent_dirs:
                uniq_parent_dirs.append(parent_dir)

            for sample_dir in samples:
                sample_parent = sample_dir.parent if sample_dir.parent != parent_dir else parent_dir
                if sample_parent not in uniq_parent_dirs:
                    uniq_parent_dirs.append(sample_parent)

        # Print the found directories grouped by their parent directories in order
        uniq_parent_dirs = {sample_dir.parent for sample_dir in samples}  # Avoids printing ~ duplicate message when no sample?? dirs are found
        for parent_dir in uniq_parent_dirs:
            print(f"\n    [bold gold1]get_samples[/]() found these directories in [bright_black bold]{parent_dir}[/]:\n")
            for sample_dir in samples:
                if sample_dir.parent == parent_dir:
                    print(f"        [bold orange_red1]{sample_dir.name}")
            print()

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


# Function decorators

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
                print(f"\nRunning: [bold gold1]{func.__name__!r}[/]{dir_string} with parameters: [bright_black]({combined_args})[/]")

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


# Other utility functions

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

def match_files(patterns, base_path=None):
    """Expand one or more glob patterns to match file paths.

    Parameters
    ----------
    patterns : str or list of str
        Glob pattern(s) to match files. Supports wildcards like '*.nii.gz', '*.tif', etc.
        Can include absolute paths with wildcards.
    base_path : str or Path, optional
        Base directory where relative patterns are applied. Defaults to the current working directory.

    Returns
    -------
    list of Path
        A sorted list of Path objects that match the provided glob patterns.

    Raises
    ------
    TypeError
        If patterns is not a string or list of strings, or base_path is not str or Path.
    ValueError
        If no files match the given patterns.
    """
    if isinstance(patterns, str):
        patterns = [patterns]
    elif not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise TypeError("patterns must be a string or a list of strings.")

    if base_path is not None and not isinstance(base_path, (str, Path)):
        raise TypeError("base_path must be a string or Path object.")

    base_path = Path.cwd() if base_path is None else Path(base_path)
    paths = []

    for pattern in patterns:
        pattern_path = Path(pattern)
        if pattern_path.is_absolute():
            paths.extend(Path(pattern_path.parent).glob(pattern_path.name))
        else:
            paths.extend(base_path.glob(pattern))

    if not paths:
        raise ValueError(f"No files found matching patterns: {patterns}")

    return sorted(paths)

def get_stem(file_path):
    """
    Get the stem of a file path by removing known compound extensions
    (e.g., '.nii.gz', '.ome.tif', '.tar.gz') and falling back to single-extension logic.

    Parameters
    ----------
    file_path : str or Path
        Path to a file.

    Returns
    -------
    str
        Stem of the file with all recognized extensions removed.
    """
    file_path = Path(file_path)
    name = file_path.name

    compound_extensions = [
        '.nii.gz',
        '.ome.tif',
        '.ome.tiff',
        '.zarr.gz',
        '.tar.gz',
        '.tar.bz2',
        '.tar.xz',
    ]

    for ext in compound_extensions:
        if str(name).endswith(ext):
            return name[: -len(ext)]
    
    return file_path.stem

@print_func_name_args_times()
def get_pad_percent(reg_outputs_path, pad_percent):
    # TODO: Could change this from reg_outputs_path to relative path to pad_percent.txt

    if pad_percent is not None:
        return pad_percent

    pad_txt = reg_outputs_path / "pad_percent.txt"
    if pad_txt.exists():
        with open(pad_txt, "r") as f:
            try:
                return float(f.read().strip())
            except ValueError:
                print("    Warning: Invalid value in pad_percent.txt. Using default pad_percent = 0.25")
    else:
        print("    Warning: pad_percent.txt not found. Using default pad_percent = 0.25")
    return 0.25