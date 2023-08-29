import sys
import nibabel as nib
from scipy import ndimage
from pathlib import Path
import numpy as np

img = nib.load(sys.argv[1]) #path/image.nii.gz

# Voxel sizes in microns
if sys.argv[2] == "m":
    x_voxel_size = img.header.get_zooms()[0]*1000
    y_voxel_size = img.header.get_zooms()[1]*1000
    z_voxel_size = img.header.get_zooms()[2]*1000
else:
    x_voxel_size = sys.argv[2]
    y_voxel_size = sys.argv[3]
    z_voxel_size = sys.argv[4]

new_voxel_size = float(sys.argv[5])

# Zoom factors:
zf_x = float(x_voxel_size)/float(new_voxel_size)
zf_y = float(y_voxel_size)/float(new_voxel_size)
zf_z = float(z_voxel_size)/float(new_voxel_size)

# Create new identity matrix
# 1st column has x resolution, 2nd y res, 3rd z res, 4th global position. 
# Position of res in columns and sign determines orientation.
# Res value determine scaling.
affine = img.affine
affine_x = affine[:,0]/zf_x
affine_y = affine[:,1]/zf_y
affine_z = affine[:,2]/zf_z
affine_position = affine[:,3]
new_affine = np.stack((affine_x,affine_y,affine_z,affine_position), axis=-1)

img_a = np.array(img.dataobj) #copies img to an ndarray (enables ndim after asarray method in scipy ndimage interpolation.py)

img_a = img_a.squeeze()

resampled_img = ndimage.zoom(img_a, (zf_x, zf_y, zf_z), order=1) #order of 0 = NN interpolation, 1 for linear

resampled_img = nib.Nifti1Image(resampled_img, new_affine) #output, identity matrix

#Copy header info from input to output:
hdr1 = img.header
hdr2 = resampled_img.header
hdr2['extents'] = hdr1['extents']
hdr2['regular'] = hdr1['regular']
hdr2['pixdim'][4:] = hdr1['pixdim'][4:]
hdr2['xyzt_units'] = hdr1['xyzt_units']
hdr2['descrip'] = hdr1['descrip']
hdr2['qform_code'] = hdr1['qform_code']
hdr2['sform_code'] = hdr1['sform_code']
hdr2['qoffset_x'] = hdr1['qoffset_x']
hdr2['qoffset_y'] = hdr1['qoffset_y']

path = Path(sys.argv[1])
period_count = path.stem.count('.') #for img.nii.gz, stem = img.nii and count = 1; count = 2 for img_0.05.nii
if period_count == 1:
    output = path.with_name(path.stem.split('.')[0] + f'_{int(new_voxel_size)}um' + "".join(path.suffixes))
elif period_count == 2:
    output = path.with_name(path.stem.split('.')[0] + "." + path.stem.split('.')[1] + f'_{int(new_voxel_size)}um' + ''.join(path.suffixes[1:]))
else:
    print (" Image name contains too many periods for the variable \"output\" in zoom.py")

# convert the array data type if specified (e.g., np.uint16)
if len(sys.argv) > 6: 
    resampled_img.header.set_data_dtype(sys.argv[6])

nib.save(resampled_img, output)

#Daniel Ryskamp Rijsketic 02/09/23-03/09/23 (Heifets lab)
