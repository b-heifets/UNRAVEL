#!/usr/bin/env python3

from fnmatch import fnmatch
import functools
import numpy as np
import nibabel as nib
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from rich import print
from rich.console import Console
from rich.table import Table
from rich.traceback import install
from tqdm import tqdm

DEFAULT_SAMPLE_DIR_PATTERN = 'sample??'

def process_samples_in_dir(process_sample_func, sample_list=None, sample_dirs_pattern=DEFAULT_SAMPLE_DIR_PATTERN, output=None, args=None):
    current_dir = Path('.').resolve().name  # Get the current directory name
    samples_to_process = sample_list or [d.name for d in Path('.').iterdir() if d.is_dir() and fnmatch(d.name, sample_dirs_pattern)]

    # Check if the list is empty. If so, use the current directory.
    if not samples_to_process:
        samples_to_process.append(current_dir)

    # Check if the current directory name is in samples_to_process
    samples_to_process = ['.' if sample == current_dir else sample for sample in samples_to_process]

    print(f"\n  [bright_black]Processing these folders: {samples_to_process}[/]\n")

    for sample in tqdm(samples_to_process):

        # Skip processing if the output file already exists
        if output:
            output_path = Path(sample, output)
            if output_path.exists():
                print(f"\n\n  [gold3]{output_path}[/] already exists. Skipping.\n")
                continue # Skip to next sample
        
        print(f"\n\n\n  Processing: [gold3]{sample}[/]")
        process_sample_func(sample, args)


####################
# Script decorator #
####################

def print_cmd_decorator(func):
    """
    A decorator to print the script name and arguments used before running the decorated function.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        cmd = f"\n\n[bold magenta]{os.path.basename(sys.argv[0])}[/] [purple3]{' '.join(sys.argv[1:])}[/]\n"
        
        console = Console()   # Instantiate the Console object
        console.print(cmd)
        
        return func(*args, **kwargs)
    return wrapper

def start_and_end_times(func):
    """
    A decorator that prints the start and end times of the function it decorates.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        print(f"  [bright_blue]Start:[/] " + start_time.strftime('%Y-%m-%d %H:%M:%S') + "\n")
        result = func(*args, **kwargs)
        end_time = datetime.now()
        print(f"\n\n\n  :mushroom: [bold magenta]{os.path.basename(sys.argv[0])}[/] [purple3]finished[/] [bright_blue]at:[/] {end_time.strftime('%Y-%m-%d %H:%M:%S')}[gold3]![/][dark_orange]![/][red1]![/] \n")
        
        return result
    return wrapper

def rich_traceback(func):
    """
    A decorator that installs rich traceback for better exception visualization.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        install()  # Enable the rich traceback
        return func(*args, **kwargs)
    
    return wrapper

def print_cmd_and_times(func):
    @functools.wraps(func)
    @print_cmd_decorator
    @start_and_end_times
    @rich_traceback
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


#########################################
# Decorators for the function_decorator #
#########################################

def timer(original_func_name): 
    """
    A decorator to time a function, print the function name, and print the arguments used.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper_timer(*args, **kwargs):
            # Convert args and kwargs to string for printing
            args_str = ', '.join(str(arg) for arg in args)
            kwargs_str = ', '.join(f"{k}={v}" for k, v in kwargs.items())
            
            # Combine both for final arguments string
            all_args = args_str
            if kwargs_str:
                all_args += ', ' + kwargs_str
                
            print(f"\n  Running: [dark_orange]{original_func_name!r}[/] [bright_black]({all_args})[/]")
            
            start_time = time.perf_counter()
            value = func(*args, **kwargs)
            end_time = time.perf_counter()
            run_time = end_time - start_time
            minutes, seconds = divmod(run_time, 60)
            if minutes == 0:
                print(f"\n  Finished in [orange_red1]{seconds:.4f}[/] seconds \n")
            else:
                print(f"\n  Finished in [orange_red1]{minutes:.0f}[/] minutes [orange_red1]{seconds:.4f}[/] seconds \n")
            return value
        return wrapper_timer
    return decorator


def task_status(message=""):
    """
    A decorator to show a console status icon spinner in bold green for tasks that are processing.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            console = Console()
            with console.status("[bold green]{}\n".format(message)) as status:
                result = func(*args, **kwargs)
                status.update("[bold green]Done!")
            return result
        return wrapper
    return decorator

def print_func_name_args_status_duration(message=""):
    """
    A decorator that combines `timer`, and `task_status`.
    """
    def decorator(func):
        original_func_name = func.__name__   # Capture the function name here
        @functools.wraps(func)
        @timer(original_func_name)
        @task_status(message=message)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

####################
# Other decorators #
####################

def save_as_nifti(ndarray, output, x_res, y_res, z_res, data_type=np.int16):

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Create the affine matrix with the appropriate resolution (converting microns to mm)
    affine = np.diag([x_res / 1000, y_res / 1000, z_res / 1000, 1])
    
    # Create and save the NIFTI image
    nifti_img = nib.Nifti1Image(ndarray, affine)
    nifti_img.header.set_data_dtype(data_type)
    nib.save(nifti_img, str(output))
    
    print(f"\n  Output: [default bold]{output}[/]\n")

def print_table(func):
    """
    A decorator that prints the result of the function it decorates in a table format using `rich`.
    The decorated function should return a list of dictionaries, where each dictionary represents a row.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        
        # If result is empty or not a list, return the result without doing anything
        if not result or not isinstance(result, list):
            return result

        # Assuming all dictionaries in the result have the same keys
        headers = result[0].keys()
        
        table = Table(show_header=True, header_style="bold magenta")
        
        # Add columns for each header
        for header in headers:
            table.add_column(header)
        
        # Populate rows
        for row_dict in result:
            table.add_row(*[str(row_dict[col]) for col in headers])

        console = Console()
        console.print(table)
        
        return result
    return wrapper