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
            print(f"\n  [bold gold3]get_samples[/]() found these directories in [bright_black bold]{parent_dir}[/]:\n")
            for sample_dir in samples:
                if sample_dir.parent == parent_dir:
                    print(f"    [bold dark_orange]{sample_dir.name}")
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
        console.print(f"\n\n[bold magenta]{os.path.basename(sys.argv[0])}[/] [bold purple3]{' '.join(sys.argv[1:])}[/]\n")
        print(f"\n  [bright_blue]Start:[/] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        return cmd
    return None

def verbose_end_msg():
    """Print the end time if verbose mode is enabled."""
    if Configuration.verbose:
        end_time = datetime.now()
        console.print(f"\n\n:mushroom: [bold magenta]{os.path.basename(sys.argv[0])}[/] [purple3]finished[/] [bright_blue]at:[/] {end_time.strftime('%Y-%m-%d %H:%M:%S')}[gold1]![/][dark_orange]![/][red1]![/] \n")
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
        return ARG_REPRESENTATIONS.get(type(arg), repr)(arg) # repr is used for unsupported types
    
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
            indent_str = '  ' * thread_local_data.indentation_level  # Using 2 spaces for each indentation level
            
            # Convert args and kwargs to string for printing
            args_str = ', '.join(arg_str_representation(arg) for arg in args)
            kwargs_str = ', '.join(f"{k}={arg_str_representation(v)}" for k, v in kwargs.items())
            combined_args = args_str + (', ' if args_str and kwargs_str else '') + kwargs_str

            # Print out the arguments with the added indent
            name = func.__name__
            if thread_local_data.indentation_level > 2:  # considering that main function is at level 1
                print(f"{indent_str}[dark_orange]{name}([/][bright_black]{args_str}{', ' + kwargs_str if kwargs_str else ''}[/][dark_orange])[/]")
            elif thread_local_data.indentation_level > 1:
                print(f"\n{indent_str}[dark_orange]{name}([/][bright_black]{args_str}{', ' + kwargs_str if kwargs_str else ''}[/][dark_orange])[/]")
            else:
                print(f"\n{indent_str}[bold gold3]{name}([/][bright_black]{combined_args}[/][bold gold3])[/]") # bold orange_red1

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
                print(f"{indent_str}[dark_orange]{duration_str}")
            else:
                print(f"\n{indent_str}[gold3]{duration_str}\n")

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
        Glob pattern(s) or explicit file paths. Wildcards like '*.nii.gz' or '*.tif' are supported.
        Both relative and absolute paths are accepted.
        When multiple patterns are provided:
            - Explicit paths preserve their order.
            - Globs are expanded and sorted within that position.
    base_path : str or Path, optional
        Base directory where relative patterns are applied.
        Defaults to the current working directory.

    Returns
    -------
    list of Path
        A list of Path objects matching the provided patterns,
        preserving explicit input order and sorting only glob expansions.

    Raises
    ------
    TypeError
        If patterns is not a string, Path, or list of such types.
    ValueError
        If no files match the given patterns.
    """
    # Normalize patterns to a list of strings
    if isinstance(patterns, (str, Path)):
        patterns = [str(patterns)]
    elif isinstance(patterns, list) and all(isinstance(p, (str, Path)) for p in patterns):
        patterns = [str(p) for p in patterns]
    else:
        raise TypeError("patterns must be a string, Path, or list of those types.")

    if base_path is not None and not isinstance(base_path, (str, Path)):
        raise TypeError("base_path must be a string or Path object.")

    base_path = Path.cwd() if base_path is None else Path(base_path)
    paths = []

    for pattern in patterns:
        pattern_path = Path(pattern)

        # Determine if it's a glob (contains wildcard characters)
        is_glob = any(ch in pattern for ch in "*?[]")

        if is_glob:
            # Absolute glob
            if pattern_path.is_absolute():
                matches = sorted(Path(pattern_path.parent).glob(pattern_path.name))
            else:
                matches = sorted(base_path.glob(pattern))
        else:
            # Explicit file path — keep as-is, resolving relative paths
            matches = [pattern_path if pattern_path.is_absolute() else base_path / pattern_path]

        paths.extend(matches)

    if not paths:
        raise ValueError(f"No files found matching patterns: {patterns}")

    return paths

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
        Stem of the file with all recognized extensions removed. E.g., path/to/file.nii.gz -> file
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

def get_extension(file_path):
    """
    Get the extension of a file path, including compound extensions.

    Parameters
    ----------
    file_path : str or Path
        Path to a file.

    Returns
    -------
    str
        The extension of the file, including compound extensions. E.g., path/to/file.nii.gz -> .nii.gz
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
            return ext
    
    return file_path.suffix

def resolve_output_paths(
    file_paths,
    output_paths=None,
    ext=None,
    stem_suffix=None,
    base_dir=None,
    *,
    skip_existing=False,
    return_inputs=False,
):
    """
    Resolve and prepare output file path(s) based on input file(s) and an optional output argument.

    The `output_paths` argument can include an optional suffix using colon notation:
        - "results/:_filtered" → output dir = "results/", suffix = "_filtered"
        - ":_processed"        → no dir, just apply suffix "_processed" next to inputs
        - "results/"           → output dir only (adds '_out' if input/output names would match)
        - "results/file.csv"   → explicit file output

    Suffix logic
    -------------
    - If input and output filenames (including extension) would match, '_out' is added automatically
      to prevent overwriting.
    - If filenames differ (e.g., due to directory, stem, or extension), no default suffix is used.
    - User-specified suffixes (via colon notation or `stem_suffix`) always take precedence.

    General rules
    -------------
    - One input, output is a file → use it directly.
    - One input, output is a directory → save inside it.
    - Multiple inputs, output must be a directory (auto-created).
    - No output → save next to each input file, adding a suffix if needed to avoid overwriting.
    - All parent directories for outputs are created automatically.

    For multiple input files in nested directories, their relative structure under `base_dir`
    is preserved automatically. If `base_dir` is not provided, it is inferred as:
        - The common parent directory of all inputs, if shared
        - Otherwise, the current working directory

    Parallel processing
    -------------------
    This function is **safe for parallel processing**.
    It ensures all parent directories exist so workers can write immediately.

    Example usage
    -------------
    >>> inputs = ["data/a.nrrd", "data/b.nrrd"]
    >>> outputs = resolve_output_paths(inputs, "results/:_aligned", ext=".nii.gz")
    >>> for i, o in zip(inputs, outputs):
    ...     print(f"{i} → {o}")
    data/a.nrrd → results/a.nii.gz
    data/b.nrrd → results/b.nii.gz

    >>> # Same format and name → '_out' added
    >>> outputs = resolve_output_paths(inputs, "results/")
    data/a.nrrd → results/a_out.nrrd

    Parameters
    ----------
    file_paths : list[str | Path]
        One or more input file paths.
    output_paths : str | Path | None, optional
        Output path with optional suffix using colon notation (e.g., 'outdir/:_filtered').
        If None, outputs are saved next to input files.
    ext : str | None, optional
        Optional override for file extension (e.g., '.csv', '.nii.gz').
        If None, keeps the input file's extension.
    stem_suffix : str | None, optional
        Manual suffix to append before the extension. Overrides any suffix in `output_paths`.
    base_dir : str | Path | None, optional
        Base directory to preserve relative paths under.
        If None, inferred automatically (common parent or CWD).
    skip_existing : bool, optional
        If True, existing outputs are skipped.
    return_inputs : bool, optional
        If True, returns (filtered_inputs, outputs).

    Returns
    -------
    list[Path]  or  (list[Path], list[Path])
        List of resolved output paths (always Path objects).
        If `return_inputs=True`, returns (filtered_inputs, outputs).
    """
    file_paths = [Path(p).resolve() for p in file_paths]
    n = len(file_paths)
    outputs = []

    # --- Parse colon notation in output_paths ---
    output_paths = str(output_paths) if output_paths is not None else ""
    parsed_suffix = None
    if ":" in output_paths:
        base_part, parsed_suffix = output_paths.split(":", 1)
        output_paths = base_part.strip() or None
        parsed_suffix = parsed_suffix.strip() or None

    # --- Infer base_dir automatically ---
    if base_dir:
        base_dir = Path(base_dir).resolve()
    elif n > 1:
        try:
            base_dir = Path(os.path.commonpath([str(f) for f in file_paths]))
        except ValueError:
            base_dir = Path.cwd()
    else:
        base_dir = file_paths[0].parent.resolve()

    # --- Determine suffix priority ---
    final_suffix = (
        stem_suffix if stem_suffix is not None
        else parsed_suffix if parsed_suffix is not None
        else ""  # decided below dynamically if needed
    )

    # --- Main logic ---
    if output_paths:
        output_paths = Path(output_paths).resolve()

        # Case 1: Single input, explicit output file
        if n == 1 and output_paths.suffix:
            output_paths.parent.mkdir(parents=True, exist_ok=True)
            outputs = [output_paths]

        # Case 2: Directory (preserve structure)
        else:
            output_paths.mkdir(parents=True, exist_ok=True)
            for f in file_paths:
                stem = get_stem(f)
                in_ext = get_extension(f)
                out_ext = ext or in_ext
                try:
                    rel = f.relative_to(base_dir)
                    rel_dir = rel.parent
                except ValueError:
                    rel_dir = Path()

                target_dir = output_paths / rel_dir
                target_dir.mkdir(parents=True, exist_ok=True)

                # Determine if name/extension match → add '_out'
                candidate = target_dir / f"{stem}{final_suffix}{out_ext}"
                if final_suffix == "" and candidate.name == f.name:
                    final_suffix = "_out"

                outputs.append(target_dir / f"{stem}{final_suffix}{out_ext}")

    else:
        # Case 3: No output path → save next to input
        for f in file_paths:
            stem = get_stem(f)
            in_ext = get_extension(f)
            out_ext = ext or in_ext
            final_suffix_for_this = final_suffix
            if final_suffix_for_this == "" and out_ext == in_ext:
                final_suffix_for_this = "_out"
            out_file = f.parent / f"{stem}{final_suffix_for_this}{out_ext}"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(out_file)

    # --- Optionally skip existing outputs ---
    if skip_existing:
        keep_idx = [i for i, p in enumerate(outputs) if not p.exists()]
        outputs = [outputs[i] for i in keep_idx]
        filtered_inputs = [file_paths[i] for i in keep_idx]
        return (filtered_inputs, outputs) if return_inputs else outputs

    return outputs

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