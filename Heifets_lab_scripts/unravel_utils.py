#!/usr/bin/env python3

from fnmatch import fnmatch
import functools
import numpy as np
import nibabel as nib
import os
import sys
import tifffile
import time
from aicspylibczi import CziFile
from datetime import datetime
from glob import glob
from lxml import etree
from pathlib import Path
from rich import print
from rich.console import Console
from rich.table import Table
from rich.traceback import install
from tifffile import imread, imwrite 
from tqdm import tqdm

##########################################
# Process all or selected sample folders #
##########################################

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


###########################
# Main function decorator #
###########################

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


######################
# Function decorator #
######################

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


###############
# Load images #
###############

def load_czi_channel(czi_path, channel):
    if czi_path:
        czi_path = czi_path[0]
        czi = CziFile(czi_path)
        ndarray = czi.read_image(C=channel)[0]
        ndarray = np.squeeze(ndarray)
        ndarray = np.transpose(ndarray, (2, 1, 0))
        return ndarray
    else:
        print(f"  [red bold]No .czi files found in {czi_path}[/]")
        return None

def load_tif_series(tif_dir_path):
    tif_path = glob(f"{tif_dir_path}/*.tif")
    if tif_path:
        ndarray = np.stack([imread(tif) for tif in tif_dir_path ], axis=-1)
        return ndarray
    else:
        print(f"  [red bold]No .tif files found in {tif_dir_path}[/]")
        return None
    

###############
# Save images #
###############

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

def save_as_tif_series(ndarray, tif_dir_out):
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    for i, slice_ in enumerate(ndarray):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"\n  Output: [default bold]{tif_dir_out}[/]\n")
    

################
# Get metadata #
################

def xyz_res_from_czi(czi_path):
    """
    Extracts metadata from .czi file and returns tuple with xy_res and z_res (voxel size) in microns.
    """
    czi = CziFile(czi_path)
    xml_root = czi.meta
    xy_res, z_res = None, None
    scaling_info = xml_root.find(".//Scaling")
    if scaling_info is not None:
        xy_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text)*1e6
        z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text)*1e6
    return xy_res, z_res

def xyz_res_from_tif(path_to_first_tif_in_series):
    """
    Extracts metadata from .ome.tif file and returns tuple with xy_res and z_res in microns.
    """
    with tifffile.TiffFile(path_to_first_tif_in_series) as tif:
        meta = tif.pages[0].tags
        ome_xml_str = meta['ImageDescription'].value
        ome_xml_root = etree.fromstring(ome_xml_str.encode('utf-8'))
        default_ns = ome_xml_root.nsmap[None]
        pixels_element = ome_xml_root.find(f'.//{{{default_ns}}}Pixels')
        xy_res, z_res = None, None
        xy_res = float(pixels_element.get('PhysicalSizeX'))
        z_res = float(pixels_element.get('PhysicalSizeZ'))
        return xy_res, z_res

###################
# Other functions #
###################

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