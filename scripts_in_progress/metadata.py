import os
import tifffile
from aicspylibczi import CziFile
import xml.etree.ElementTree as ET

def search_for_file(extensions, directories):
    """
    Search for files with a given list of extensions in the specified directories.

    :param extensions: List of file extensions to search for.
    :param directories: List of directories to search in.
    :return: Full path of the found file or None if not found.
    """
    for directory in directories:
        for file in os.listdir(directory):
            for ext in extensions:
                if file.endswith(ext):
                    return os.path.join(directory, file)
    return None

def rename_files_with_spaces(directory):
    """
    Rename files in the given directory by replacing spaces with underscores.

    :param directory: Path to the directory.
    """
    if os.path.exists(directory):
        for file in os.listdir(directory):
            if ' ' in file:
                src = os.path.join(directory, file)
                dst = os.path.join(directory, file.replace(' ', '_'))
                os.rename(src, dst)

def get_metadata_from_tif(image_path):
    """
    Extracts metadata from TIFF file.

    :param image_path: Path to the TIFF file.
    :return: Tuple of SizeX, SizeY, SizeZ, x_res, y_res, z_res in microns.
    """
    with tifffile.TiffFile(image_path) as tif:
        image = tif.asarray()
        meta = tif.pages[0].tags
        print(meta)
        # Get image dimensions based on shape
        if len(image.shape) == 3:
            SizeZ, SizeY, SizeX = image.shape
        else:
            SizeX, SizeY = image.shape
            SizeZ = 1

        # Extract X and Y resolution values and convert to microns
        x_res = extract_resolution_in_microns(meta['XResolution'].value)
        y_res = extract_resolution_in_microns(meta['YResolution'].value)

        # Guess for z resolution since TIFF might not contain Z resolution
        z_res = 1  # This value can be adjusted if needed

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
    current_dir = os.getcwd()
    parameters_dir = os.path.join(current_dir, "parameters")
    os.makedirs(parameters_dir, exist_ok=True)
    metadata_path = os.path.join(parameters_dir, "metadata")

    if not os.path.exists(metadata_path):
        czi_file = search_for_file(['.czi'], [current_dir])
        
        if czi_file:
            SizeX, SizeY, SizeZ, x_res, y_res, z_res = get_metadata_from_czi(czi_file)
        else:
            tif_directories = [current_dir, os.path.join(current_dir, "488_original"), os.path.join(current_dir, "488")]
            for directory in tif_directories:
                rename_files_with_spaces(directory)
                
            tif_file = search_for_file(['.tif', '.tiff'], tif_directories)
            
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