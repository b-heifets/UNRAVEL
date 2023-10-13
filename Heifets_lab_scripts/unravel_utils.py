#!/usr/bin/env python3

import functools
import numpy as np
import os
import sys
import time
from config import Configuration
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from rich import print
from rich.console import Console
from rich.progress import Progress, TextColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn, ProgressColumn
from rich.text import Text


######## Sample list ########

def get_samples(dir_list=None, dir_pattern="sample??"):
    """Return a list of sample folders or the current directory if no sample folders are found."""
    if dir_list:
        samples = [Path(dir_name).name for dir_name in dir_list if Path(dir_name).is_dir()]
    else:
        current_dir = Path('.').resolve().name
        samples = [
            d.name if d.name != current_dir else '.'
            for d in Path('.').iterdir()
            if d.is_dir() and fnmatch(d.name, dir_pattern)
        ]
    if not samples:
        samples.append('.')
    return sorted(samples)


######## Progress bar ########

class AverageTimePerIterationColumn(ProgressColumn):
    def render(self, task: "Task") -> Text:
        speed = task.speed or 0 
        if speed > 0:
            avg_time = f"{1 / speed:.2f}s/iter"
        else:
            avg_time = "." 
        return Text(avg_time, style="red1")
    
class CustomTimeRemainingColumn(TimeRemainingColumn):
    def render(self, task) -> Text:
        time_elapsed = super().render(task)
        time_elapsed.stylize("dark_orange")      
        return time_elapsed
    
class CustomTimeElapsedColumn(TimeElapsedColumn):
    def render(self, task) -> Text:
        time_elapsed = super().render(task)
        time_elapsed.stylize("gold1")      
        return time_elapsed

class CustomMofNCompleteColumn(MofNCompleteColumn):
    def render(self, task) -> Text:
        completed = str(task.completed)
        total = str(task.total)
        return Text(f"{completed}/{total}", style="green") 

def get_progress_bar(task_message="[red]Processing samples...", total_tasks=None):
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        SpinnerColumn(style="bright_magenta"),
        BarColumn(complete_style="purple3", finished_style="purple"),
        TextColumn("[bright_blue]{task.percentage:>3.0f}[bright_cyan]%[progress.percentage]"),
        CustomMofNCompleteColumn(),
        CustomTimeElapsedColumn(),
        CustomTimeRemainingColumn(),
        AverageTimePerIterationColumn()
    )
    return progress


######## Main function decorator ########

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
        print(f"  [bright_blue]Start:[/] " + start_time.strftime('%Y-%m-%d %H:%M:%S') + "\n")

        result = func(*args, **kwargs)  # Call the original function

        # End time
        end_time = datetime.now()
        print(f"\n\n  :mushroom: [bold bright_magenta]{os.path.basename(sys.argv[0])}[/] [purple3]finished[/] [bright_blue]at:[/] {end_time.strftime('%Y-%m-%d %H:%M:%S')}[gold1]![/][dark_orange]![/][red1]![/] \n")
        return result

    return wrapper


######## Function decorator ########

def print_func_name_args_times(arg_index_for_basename=None):
    """A decorator that prints the function name, arguments, duration, and memory usage of the function it decorates."""
    
    ARG_REPRESENTATIONS = {
        np.ndarray: lambda x: f"ndarray: {x.shape} {x.dtype}",
        str: str,
        int: str,
        float: str,
        Path: str
    }

    def arg_str_representation(arg):
        """Return a string representation of the argument passed to the decorated function."""
        return ARG_REPRESENTATIONS.get(type(arg), str)(arg) 

    def decorator(func):
        @functools.wraps(func)
        def wrapper_timer(*args, **kwargs):
            if not Configuration.verbose:
                return func(*args, **kwargs)  # If not verbose, skip all additional logic
            
            # Convert args and kwargs to string for printing
            args_str = ', '.join(arg_str_representation(arg) for arg in args)
            kwargs_str = ', '.join(f"{k}={arg_str_representation(v)}" for k, v in kwargs.items())

            # Get the parent folder name (e.g., sample folder name) of the first argument if arg_index_for_basename is not None
            parent_folder_from_arg = args[arg_index_for_basename].parent.name if arg_index_for_basename is not None else os.path.basename(os.getcwd())

            # Print out the arguments
            print(f"\n  Running: [bold gold1]{func.__name__!r}[/] for [bold dark_orange]{parent_folder_from_arg}[/] \n\n  [bright_black]({args_str}{', ' + kwargs_str if kwargs_str else ''})\n")

            # Function execution
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()

            # Print duration
            run_time = end_time - start_time
            minutes, seconds = divmod(run_time, 60)
            duration_str = f"{minutes:.0f} min {seconds:.4f} sec" if minutes else f"{seconds:.4f} sec"
            print(f"  Finished in [orange_red1]{duration_str}[/] \n")
            
            return result
    
        return wrapper_timer
    return decorator