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
from rich.progress import Progress, TextColumn, SpinnerColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn, ProgressColumn
from rich.table import Table
from rich.text import Text
from tifffile import imread, imwrite 


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

def get_progress_bar(task_message="[red]Processing samples...", total_tasks=None):
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        SpinnerColumn(style="bright_magenta"),
        BarColumn(complete_style="purple3", finished_style="purple"),
        TimeRemainingColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn("[dark_orange]{task.percentage:>3.0f}%[progress.percentage]"),
        AverageTimePerIterationColumn()
    )
    return progress


######## Main function decorator ########

def print_cmd_and_times(func):
    """A combined decorator to print the script name, arguments, start/end times, and use rich traceback."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if print_cmd_and_times.verbose:
            # Print command
            cmd = f"\n\n[bold magenta]{os.path.basename(sys.argv[0])}[/] [purple3]{' '.join(sys.argv[1:])}[/]\n"
            console = Console()  # Instantiate the Console object
            console.print(cmd)

            # Start time
            start_time = datetime.now()
            print(f"  [bright_blue]Start:[/] " + start_time.strftime('%Y-%m-%d %H:%M:%S') + "\n")

        result = func(*args, **kwargs)  # Call the original function

        if print_cmd_and_times.verbose:
            # End time
            end_time = datetime.now()
            print(f"\n\n  :mushroom: [bold magenta]{os.path.basename(sys.argv[0])}[/] [purple3]finished[/] [bright_blue]at:[/] {end_time.strftime('%Y-%m-%d %H:%M:%S')}[gold3]![/][dark_orange]![/][red1]![/] \n")

        return result
    return wrapper

print_cmd_and_times.verbose = False 


######## Function decorator ########

def print_func_name_args_times(func):
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

    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        if not print_func_name_args_times.verbose:
            return func(*args, **kwargs)  # If not verbose, skip all additional logic
        
        # Convert args and kwargs to string for printing
        args_str = ', '.join(arg_str_representation(arg) for arg in args)
        kwargs_str = ', '.join(f"{k}={arg_str_representation(v)}" for k, v in kwargs.items())

        # Print out the arguments
        print(f"\n  Running: [bold gold3]{func.__name__!r}[/] [bright_black]({args_str}{', ' + kwargs_str if kwargs_str else ''})\n")

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

print_cmd_and_times.verbose = False 


######## Load images ########

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


######## Get metadata ########

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


######## Save images ########

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