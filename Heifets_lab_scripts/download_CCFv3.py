#!/usr/bin/env python3

from allensdk.api.queries.reference_space_api import ReferenceSpaceApi

# Initialize the API
api = ReferenceSpaceApi()

# Specify the CCF version
ccf_version = 'annotation/ccf_2017'

# Specify the resolutions you are interested in
resolutions = [10, 25]

# Loop through each resolution to download both the atlas and template volumes
for resolution in resolutions:
    # Define file names for the atlas and template volumes
    atlas_file_name = f'ccf_{ccf_version}_atlas_{resolution}um.nrrd'
    template_file_name = f'ccf_{ccf_version}_template_{resolution}um.nrrd'
    
    # Download the atlas volume
    print(f"Downloading CCFv3 atlas at {resolution} micron resolution...")
    api.download_annotation_volume(ccf_version, resolution, atlas_file_name)
    print(f"Atlas downloaded and saved as {atlas_file_name}")
    
    # Download the template volume
    print(f"Downloading CCFv3 template at {resolution} micron resolution...")
    api.download_template_volume(resolution, template_file_name)
    print(f"Template downloaded and saved as {template_file_name}")

print("Downloads completed.")