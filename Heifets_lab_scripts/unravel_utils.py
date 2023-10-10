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
from functools import wraps, partial
from lxml import etree
from pathlib import Path
from rich import print
from rich.console import Console
from rich.progress import Progress, TextColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.table import Table
from rich.traceback import install
from tifffile import imread, imwrite 

#############################################################################
# Process a specified path/image, all sample?? folders, or selected folders #
#############################################################################

DEFAULT_SAMPLE_DIR_PATTERN = 'sample??'

def process_single_input(input_path, func, args):
    """Process a single input path/image."""
    img_path = Path(input_path)
    if img_path.exists():
        print(f"\n\n\n  Processing: [gold3]{img_path}[/]")
        func(img_path.parent, args=args) 
    else:
        print(f"\n\n\n  [red]Error: Invalid file path. Please provide a valid path/image")

def get_progress():
    """Return a configured progress object for the progress bar."""
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        # BarColumn(),
        SpinnerColumn(style="bright_magenta"),
        BarColumn(complete_style="purple3",  finished_style="purple"),
        TimeRemainingColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(), 
        TextColumn("[dark_orange]{task.percentage:>3.0f}%[progress.percentage]")

    )
    return progress

def process_with_progress(items, func, *func_args, progress_message="  [red]Processing...", **func_kwargs):
    """Process items with a progress bar."""
    with get_progress() as progress:
        task = progress.add_task(progress_message, total=len(items))
        for item in items:
            # Use functools.partial to pre-apply the other arguments
            partial_func = partial(func, item, *func_args, **func_kwargs)
            partial_func() 
            progress.update(task, advance=1)

def process_samples_in_dir(process_sample_func, sample_list=None, sample_dirs_pattern=DEFAULT_SAMPLE_DIR_PATTERN, output=None, args=None):
    """Get a list of samples to process and process them with a progress bar."""
    current_dir = Path('.').resolve().name  # Get the current directory name
    samples_to_process = sorted(sample_list or [d.name for d in Path('.').iterdir() if d.is_dir() and fnmatch(d.name, sample_dirs_pattern)])

    # Check if the list is empty. If so, use the current directory.
    if not samples_to_process:
        samples_to_process.append(current_dir)

    # Check if the current directory name is in samples_to_process
    samples_to_process = ['.' if sample == current_dir else sample for sample in samples_to_process]

    print(f"\n  [bright_black]Processing these folders: {samples_to_process}[/]\n")

    # Utilizing process_with_progress
    def wrapped_process_sample(sample):
        # Skip processing if the output file already exists
        if output:
            output_path = Path(sample, output)
            if output_path.exists():
                print(f"\n\n  [gold3]{output_path}[/] already exists. Skipping.\n")
                return  # Exit current iteration
        
        print(f"\n\n\n  Processing: [gold3]{sample}[/]")
        process_sample_func(sample, args=args)

    process_with_progress(samples_to_process, wrapped_process_sample, progress_message="  [red]Processing samples...")


###########################
# Main function decorator #
###########################

def print_cmd_decorator(func):
    """A decorator to print the script name and arguments used before running the decorated function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        cmd = f"\n\n[bold magenta]{os.path.basename(sys.argv[0])}[/] [purple3]{' '.join(sys.argv[1:])}[/]\n"
        
        console = Console()   # Instantiate the Console object
        console.print(cmd)
        
        return func(*args, **kwargs)
    return wrapper

def start_and_end_times(func):
    """A decorator that prints the start and end times of the function it decorates."""
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
    """A decorator that installs rich traceback for better exception visualization."""
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
def print_func_name_args_times(func):
    """A decorator that prints the function name, arguments, and duration of the function it decorates."""
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        # Convert args and kwargs to string for printing
        args_str = ', '.join(str(arg) for arg in args)
        kwargs_str = ', '.join(f"{k}={v}" for k, v in kwargs.items())

        # Combine both for final arguments string
        all_args = args_str
        if kwargs_str:
            all_args += ', ' + kwargs_str

        # Print out the arguments
        print(f"\n  Running: [dark_orange]{func.__name__!r}[/] [bright_black]({all_args})\n")

        start_time = time.perf_counter()
        value = func(*args, **kwargs)  # Pass all arguments to the function
        end_time = time.perf_counter()
        run_time = end_time - start_time
        minutes, seconds = divmod(run_time, 60)
        if minutes == 0:
            print(f"  Finished in [orange_red1]{seconds:.4f}[/] seconds \n")
        else:
            print(f"  Finished in [orange_red1]{minutes:.0f}[/] minutes [orange_red1]{seconds:.4f}[/] seconds \n")
        return value
    return wrapper_timer


###############
# Load images #
###############

def load_czi_channel(czi_path, channel):
    """Load a channel from a .czi image and return it as a numpy array."""
    if czi_path:
        czi = CziFile(czi_path)
        ndarray = czi.read_image(C=channel)[0]
        ndarray = np.squeeze(ndarray)
        ndarray = np.transpose(ndarray, (2, 1, 0))
        return ndarray
    else:
        print(f"  [red bold].czi file not found: {czi_path}[/]")
        return None
    
def load_nii(img_path):
    """Load a .nii.gz image and return it as a numpy array."""
    if img_path:
        img = nib.load(img_path)
        ndarray = img.get_fdata()
        return ndarray
    else:
        print(f"  [red bold].nii.gz file note found: {img_path}[/]")
        return None
    
def load_tifs(tif_dir_path): 
    """Load a series of .tif images and return them as a numpy array."""
    tifs = glob(f"{tif_dir_path}/*.tif")
    if tifs:
        tifs_sorted = sorted(tifs)
        tifs_stacked = [imread(tif) for tif in tifs_sorted]
        ndarray = np.stack(tifs_stacked, axis=0)  # stack along the first dimension (z-axis)
        return ndarray # shape: z, y, x
    else:
        print(f"  [red bold]No .tif files found in {tif_dir_path}[/]")
        return None

###############
# Save images #
###############

def save_as_nii(ndarray, output, x_res, y_res, z_res, data_type):
    """Save a numpy array as a .nii.gz image."""

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    # Reorient ndarray
    ndarray = np.transpose(ndarray, (2, 1, 0))
    
    # Create the affine matrix with the appropriate resolutions (converting microns to mm)
    affine = np.diag([x_res / 1000, y_res / 1000, z_res / 1000, 1])
    
    # Create and save the NIFTI image
    nifti_img = nib.Nifti1Image(ndarray, affine)
    nifti_img.header.set_data_dtype(data_type)
    nib.save(nifti_img, str(output))
    
    print(f"\n  Output: [default bold]{output}[/]\n")

def save_as_tifs(ndarray, tif_dir_out):
    """Save a numpy array as a series of .tif images."""
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    for i, slice_ in enumerate(ndarray):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"\n  Output: [default bold]{tif_dir_out}[/]\n")
    

################
# Get metadata #
################

def xyz_res_from_czi(czi_path):
    """Extract metadata from .czi file and returns tuple with xy_res and z_res (voxel size) in microns."""
    czi = CziFile(czi_path)
    xml_root = czi.meta
    xy_res, z_res = None, None
    scaling_info = xml_root.find(".//Scaling")
    if scaling_info is not None:
        xy_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text)*1e6
        z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text)*1e6
    return xy_res, z_res

def xyz_res_from_tif(path_to_first_tif_in_series):
    """Extract metadata from .ome.tif file and returns tuple with xy_res and z_res in microns."""
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