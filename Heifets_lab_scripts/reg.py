#!/usr/bin/env python3

import argparse
import subprocess
import nibabel as nib
import sys
from scipy.ndimage import zoom, gaussian_filter
from ants import registration, apply_transforms_to_image


print('''

DRAFT IN PROGRESS

      ''')


def parse_args():
    parser = argparse.ArgumentParser(description='Registers average template brain/atlas to downsampled autofl brain. Check accuracy w/ ./reg_final outputs in itksnap or fsleyes')
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='')
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='')
    parser.add_argument('-i', '--input', help='path/img.nii.gz', default=1, metavar='')
    parser.add_argument('-oc', '--ort_code', help='3 letter orientation code (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior; Default: ALI)', default='ALI', metavar='')
    parser.add_argument('-an', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", metavar='')
    parser.add_argument('-a', '--atlas', help='<path/atlas> to warp (default: gubra_ano_split_10um.nii.gz)', default="/usr/local/gubra/gubra_ano_split_25um.nii.gz", metavar='')
    parser.add_argument('-r', '--res', help="Resolution of atlas in microns (10, 25, or 50; Default: 25)", default=25, type=int, metavar='')
    parser.add_argument('-s', '--side', help="Side for hemisphere registration (w, l or r; Default: w)", default='w', metavar='')
    parser.add_argument('-t', '--template', help='Template (moving img; Default: path/gubra_template_25um.nii.gz)', default="/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz",  metavar='')
    parser.add_argument('-m', '--mask', help="<brain_mask>.nii.gz", default=None, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns (Default: 50)', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    return parser.parse_args()

def check_ants_path():
    try:
        ants_path = subprocess.check_output(["which", "antsRegistration"]).decode('utf-8').strip()
        
        if not ants_path:
            raise FileNotFoundError("ANTS program can't be found. Please (re)define $ANTSPATH in your environment.")
        
        print("\nANTS path check: OK...")
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ANTS program can't be found. Please (re)define $ANTSPATH in your environment.")
        sys.exit(1)

def load_nifti_image(file_path):
    return nib.load(file_path).get_fdata()

def save_nifti_image(image_data, reference_path, save_path):
    img = nib.Nifti1Image(image_data, nib.load(reference_path).affine)
    nib.save(img, save_path)

def bias_correction(image_path, mask_path=None):
    from ants import n4_bias_field_correction
    
    image = nib.load(image_path)
    if mask_path:
        mask = nib.load(mask_path)
        corrected_image = n4_bias_field_correction(image, mask)
    else:
        corrected_image = n4_bias_field_correction(image)
    
    corrected_path = "corrected_" + image_path.split('/')[-1]
    nib.save(corrected_image, corrected_path)
    return corrected_path

def pad_image(image_path, pad_width=0.15):
    """Pads image by 15% of voxels on all sides"""
    image_data = load_nifti_image(image_path)
    pad_width = int(pad_width * image_data.shape[0])
    padded_img = np.pad(image_data, [(pad_width, pad_width)] * 3, mode='constant')
    return padded_img

def smooth_image(image_path):
    image_data = load_nifti_image(image_path)
    smoothed_data = gaussian_filter(image_data, sigma=0.25)  # adjust sigma if needed

    smoothed_path = "smoothed_" + image_path.split('/')[-1]
    save_nifti_image(smoothed_data, image_path, smoothed_path)
    return smoothed_path


def main(args):

    args = parse_args()

    check_ants_path()

    if len(args.ort_code) != 3 or not all(x in 'APRLIS' for x in args.ort_code):
        raise ValueError("Invalid 3 letter orientation code: Open z-stack virtually in FIJI -> 1st letter is side facing up, 2nd is side facing left, 3rd is side at stack start")

    input_data = load_nifti_image(args.input)
    
    # Downsample to 50 microns
    resampled_data = zoom(input_data, (0.05, 0.05, 0.05), order=3)
    save_nifti_image(resampled_data, args.input, "resampled_image.nii.gz")

    # Bias correction
    corrected_path = bias_correction("resampled_image.nii.gz", args.mask)
    
    # Padding
    padded_path = pad_image(corrected_path)

    # Smoothing
    smoothed_path = smooth_image(padded_path)

    # For example, with ANTsPy
    fixed_image = nib.load("resampled_image.nii.gz")
    moving_image = nib.load(args.template)
    
    reg_output = registration(fixed_image, moving_image)
    warped_moving_image = apply_transforms_to_image(fixed_image, moving_image, transform=reg_output['fwdtransforms'])
    save_nifti_image(warped_moving_image.numpy(), args.input, "warped_moving_image.nii.gz")

    # More operations...
    # ...

if __name__ == "__main__":
    main()