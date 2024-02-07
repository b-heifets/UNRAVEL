#!/usr/bin/env python3

import functools
import numpy as np
import os
import sys
import threading
import time
from unravel_config import Configuration
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from rich import print
from rich.console import Console
from rich.progress import Progress, TextColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn, ProgressColumn
from rich.text import Text


# Sample list 

def get_samples(sample_dir_list=None, sample_dir_pattern="sample??", exp_dir_paths=None):
    """Return a list of sample folders from the provided directory list or experiment directories.
    If no sample folders are found, return the current directory."""
    samples = []

    # If sample_dir_list is provided, add directories from it that exist.
    if sample_dir_list:
        samples += [Path(dir_name).name for dir_name in sample_dir_list if Path(dir_name).is_dir()]

    # If exp_dir_paths is provided, search for sample folders within each experiment directory.
    if exp_dir_paths:
        for exp_dir in exp_dir_paths:
            exp_path = Path(exp_dir)
            if exp_path.is_dir():
                samples += [
                    d.name for d in exp_path.iterdir()
                    if d.is_dir() and fnmatch(d.name, sample_dir_pattern)
                ]

    # If no sample_dir_list or exp_dir_paths provided, or no samples found in them, search in the current working directory.
    if not samples:
        cwd = Path.cwd()
        samples += [
            d.name if d.name != cwd.name else '.' 
            for d in Path('.').iterdir()
            if d.is_dir() and fnmatch(d.name, sample_dir_pattern)
        ]

    # Replace single '.' with the current directory name, if necessary.
    if samples == ['.']:
        samples[0] = cwd.name

    return sorted(samples)


# Progress bar

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
    def render(self, task: "Task") -> Text:
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


# Main function decorator

def print_cmd_and_times(func):
    """A combined decorator to print the script name, arguments, start/end times, and use rich traceback."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not Configuration.verbose:
            return func(*args, **kwargs)  # If not verbose, skip all additional logic

        # Print command
        cmd = f"\n\n[bold bright_magenta]{os.path.basename(sys.argv[0])}[/] [purple3]{' '.join(sys.argv[1:])}[/]\n"
        console = Console()  # Instantiate the Console object
        console.print(cmd)

        # Start time
        start_time = datetime.now()
        print(f"    [bright_blue]Start:[/] " + start_time.strftime('%Y-%m-%d %H:%M:%S') + "\n")

        result = func(*args, **kwargs)  # Call the original function

        # End time
        end_time = datetime.now()
        print(f"\n\n:mushroom: [bold bright_magenta]{os.path.basename(sys.argv[0])}[/] [purple3]finished[/] [bright_blue]at:[/] {end_time.strftime('%Y-%m-%d %H:%M:%S')}[gold1]![/][dark_orange]![/][red1]![/] \n")
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