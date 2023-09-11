#!/usr/bin/env python3

import functools
import os
import re
import sys
import time
from datetime import datetime
from rich import print
from rich.console import Console
from rich.table import Table
from rich.traceback import install


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
    A decorator to time a function
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

def function_decorator(message=""):
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