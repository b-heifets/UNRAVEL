"""
Script to extract metadata from TIFF and CZI files and save to a metadata file.
"""

import os
from pathlib import Path
import tifffile
from aicspylibczi import CziFile
from lxml import etree

def search_for_file(extensions, directories):
    """
    Search for files with given extensions in the specified directories.

    :param extensions: Tuple of file extensions to search for.
    :param directories: List of directories to search in.
    :return: Full path of found file or None if not found.
    """
    for directory in directories:
        for file in os.listdir(directory):
            if file.endswith(extensions):
                return Path(directory) / file
    return None

def rename_files_with_spaces(directory):
    """
    Rename files in the given directory by replacing spaces with underscores.

    :param directory: Path to the directory.
    """
    directory = Path(directory)
    if directory.exists():
        for file in directory.iterdir():
            if ' ' in file.name:
                dst = directory / file.name.replace(' ', '_')
                file.rename(dst)

def get_metadata_from_tif(image_path):
    """
    Extracts metadata from TIFF file.

    :param image_path: Path to the TIFF file.
    :return: Tuple of SizeX, SizeY, SizeZ, x_res, y_res, z_res in microns.
    """
    with tifffile.TiffFile(image_path) as tif:
        image_shape = tif.pages[0].shape
        meta = tif.pages[0].tags

        # Get image dimensions based on shape
        if len(image_shape) == 2:
            SizeX, SizeY = image_shape
            SizeZ = 1
        elif len(image_shape) == 3:
            SizeZ, SizeY, SizeX = image_shape
        else:
            # Handle 4D image shape
            # Depending on your TIFF's actual structure
            _, SizeZ, SizeY, SizeX = image_shape

        # Default voxel size values
        x_res, y_res, z_res = 1, 1, 1
        if "ome.tif" in str(image_path):
            ome_xml_str = meta['ImageDescription'].value
            ome_xml_root = etree.fromstring(ome_xml_str.encode('utf-8'))
            namespaces = {k: v for k, v in ome_xml_root.nsmap.items() if k is not None}
            default_ns = ome_xml_root.nsmap[None]
            pixels_element = ome_xml_root.find(f'.//{{{default_ns}}}Pixels')
            voxel_size_x = float(pixels_element.get('PhysicalSizeX'))
            voxel_size_y = float(pixels_element.get('PhysicalSizeY'))
            voxel_size_z = float(pixels_element.get('PhysicalSizeZ'))

        else:
            # Extract X and Y resolution values and convert to microns
            x_res = meta['XResolution'].value[0]
            y_res = meta['YResolution'].value[0]

    return SizeX, SizeY, SizeZ, x_res, y_res, z_res

def extract_resolution_in_microns(resolution):
    """
    Convert TIFF resolution to microns.

    :param resolution: Resolution from TIFF metadata.
    :return: Resolution in microns.
    """
    if isinstance(resolution, tuple) and len(resolution) == 2:
        # Convert pixels per inch to microns per pixel
        return 25400 / resolution[0]
    return resolution

def get_metadata_from_czi(image_path):
    """
    Extracts metadata from CZI file.

    :param image_path: Path to the CZI file.
    :return: Tuple of SizeX, SizeY, SizeZ, x_res, y_res, z_res in microns.
    """
    czi = CziFile(image_path)
    size = czi.size
    SizeZ, SizeY, SizeX = size[-3:]

    # Default voxel size values
    x_res, y_res, z_res = 1, 1, 1

    # Extract voxel sizes from XML metadata
    xml_root = czi.meta
 
    scaling_info = xml_root.find(".//Scaling")
    if scaling_info is not None:
        x_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text)*1e6
        y_res = float(scaling_info.find("./Items/Distance[@Id='Y']/Value").text)*1e6
        z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text)*1e6

    return SizeX, SizeY, SizeZ, x_res, y_res, z_res

def main():
    current_dir = Path.cwd()
    parameters_dir = current_dir / "parameters"
    parameters_dir.mkdir(exist_ok=True)
    metadata_path = parameters_dir / "metadata"

    if not metadata_path.exists():
        # Search for CZI or TIFF file
        czi_file = search_for_file(('.czi'), [current_dir])
        
        if czi_file:
            SizeX, SizeY, SizeZ, x_res, y_res, z_res = get_metadata_from_czi(czi_file)
        else:
            tif_directories = [current_dir, current_dir / "488_original", current_dir / "488"]
            for directory in tif_directories:
                rename_files_with_spaces(directory)
            tif_file = search_for_file(('.tif', '.tiff'), tif_directories)
            
            if tif_file:
                SizeX, SizeY, SizeZ, x_res, y_res, z_res = get_metadata_from_tif(tif_file)

        # Write metadata to the file
        with open(metadata_path, 'w') as meta_file:
            for i in range(1, 10):
                meta_file.write(f"{i}\n")
            meta_file.write(f"SizeX = {SizeX}\n")
            meta_file.write(f"SizeY = {SizeY}\n")
            meta_file.write(f"SizeZ = {SizeZ}\n")
            meta_file.write(f"Voxel size: {x_res:.4f}x{y_res:.4f}x{z_res:.4f} micron^3\n")

if __name__ == "__main__":
    main()