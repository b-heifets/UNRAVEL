#!/usr/bin/env python3

from __future__ import print_function # Python 2/3 compatibility
import multiprocessing
import psutil
import os
import argparse
import h5py
import vigra
import numpy as np
from pathlib import Path
from rich.live import Live
from rich.progress import Progress

from ilastik import app
from ilastik.applets.dataSelection import PreloadedArrayDatasetInfo
from ilastik.workflows.pixelClassification import PixelClassificationWorkflow

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, resolve_path
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Run ilastik headless pixel classification.', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-ilp', '--ilastik_project', help='path/project.ilp', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Full res image input path relative (rel_path) to ./sample??', required=True, action=SM)
    parser.add_argument('-o', '--output', help='rel_path/segmented_img.h5 (default: ilastik/segmented_img.h5)', default="ilastik/segmented_img.h5", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Run script from the experiment directory w/ sample?? folder(s)
or run from a sample?? folder.

Usage: /path/to/ilastik-1.x.x/bin/python /path/to/ilastik.py -i rel_path/full_res_img -o rel_path/segmented_img.h5 -ilp /path/to/your/project.ilp

Next script: validate_clusters.py or apply_mask.py"""
    return parser.parse_args()


def set_environment_variables():
    """ Setup environment variables for resource management. 
    
    LAZYFLOW_THREADS: Number of CPU cores to use.
    LAZYFLOW_TOTAL_RAM_MB: Total RAM to use in megabytes (set to 80% of total RAM)."""

    # Number of available CPU cores
    cpu_cores = multiprocessing.cpu_count()
    os.environ["LAZYFLOW_THREADS"] = str(cpu_cores)

    # Total RAM in megabytes
    ram_mb = psutil.virtual_memory().total // 1024**2
    # Setting the RAM environment variable to use 80% of total RAM
    os.environ["LAZYFLOW_TOTAL_RAM_MB"] = str(int(0.8 * ram_mb))

    print(f"Configured to use {cpu_cores} cores and {int(0.8 * ram_mb)} MB of RAM.")


@print_func_name_args_times()
def array_to_hdf5_3d(image_array, hdf5_path, dataset_name='data'):
    """
    Convert a 3D single-channel NumPy array to an HDF5 file with optional compression.

    Parameters:
    - image_array: NumPy array containing the 3D image data.
    - hdf5_path: String, path where the HDF5 file will be saved.
    - dataset_name: String, the name of the dataset within the HDF5 file.
    """
    # Assuming the image_array is in the shape of (z, y, x) and contains one channel per voxel
    # Apply Vigra axistags for a 3D single-channel volume
    image_array = vigra.taggedView(image_array, axistags='zyx')

    with h5py.File(hdf5_path, 'w') as hdf5_file:
        hdf5_file.create_dataset(dataset_name, data=image_array, compression='gzip')

@print_func_name_args_times()
def ilastik_pixel_classification(project_path, ndarray, hdf5_path):
    """Run ilastik headless pixel classification on a 3D ndarray and save the predictions to an HDF5 file.
    
    Parameters:
    - project_path: String, path to the ilastik project file (.ilp).
    - ndarray: 3D NumPy array containing the image data.
    - hdf5_path: String, path where the HDF5 file will be saved."""

    # Configure ilastik command-line arguments and load the project
    args = app.parse_args([])
    args.headless = True
    args.project = project_path
    shell = app.main(args)
    assert isinstance(shell.workflow, PixelClassificationWorkflow)

    # Process the ndarray
    input_data = vigra.taggedView(ndarray, axistags='zyx')
    dataset_info = PreloadedArrayDatasetInfo(preloaded_array=input_data)
    role_data_dict = {'Raw Data': [dataset_info]}

    # Run the export
    predictions = shell.workflow.batchProcessingApplet.run_export(role_data_dict, export_to_array=True)

    # Save predictions to HDF5
    with h5py.File(hdf5_path, 'w') as hdf5_file:
        hdf5_file.create_dataset('predictions', data=predictions[0], compression='gzip')


def main():

    set_environment_variables()

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define output
            output = resolve_path(sample_path, args.output, make_parents=True)
            if output.exists():
                print(f"\n\n    {output.name} already exists. Skipping.\n")
                continue

            # Define input image path
            img_path = resolve_path(sample_path, args.input)

            # Load the full resolution immunofluorescence image
            img = load_3D_img(img_path, "zyx")

            # Perform pixel classification using the ilastik project
            ilastik_pixel_classification(args.ilastik_project, img, output)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()