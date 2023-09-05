#!/usr/bin/env python3
# Maged Goubran @ 2017, mgoubran@stanford.edu 
### Simplified by Dan Rijsketic 07/25/23 (Heifets lab)

import argparse, cv2, glob, multiprocessing, os, sys, re
import numpy as np
import nibabel as nib
import scipy.ndimage
from datetime import datetime
from joblib import Parallel, delayed

def parsefn():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--folder', type=str, required=True, help="Input directory of tifs")
    parser.add_argument('-d', '--down', type=int, default=8, help="Downsample ratio")
    parser.add_argument('-o', '--outnii', type=str, required=True, help="Output nii name")
    parser.add_argument('-vx', '--resx', type=float, default=5, help="Resolution in x-y plane in um")
    parser.add_argument('-vz', '--resz', type=float, default=5, help="Thickness (z-axis resolution) in um")
    return parser

def numericalsort(value):
    numbers = re.compile(r'(\d+)')
    parts = numbers.split(value)
    parts[1::2] = map(int, parts[1::2])
    return parts

def converttiff2nii(d, i, x, newdata, tifx):
    down = (1.0 / int(d))
    m = cv2.imread(x, -1) 
    inter = cv2.INTER_CUBIC if tifx < 5000 else cv2.INTER_NEAREST 
    newdata[i, :, :] = cv2.resize(m, (0, 0), fx=down, fy=down, interpolation=inter)

def savenii(newdata, d, outnii, vx, vz):
    outvox = vx * d 
    dz = d if vx <= vz else int(d * float(vx / vz))
    outz = vz * dz 
    mat = np.eye(4) * outvox
    mat[2, 2] = outz
    mat[3, 3] = 1
    data_array = np.rollaxis(newdata, 0, 3)
    down = (1.0 / int(dz))
    data_array = scipy.ndimage.zoom(data_array, [1, 1, down], order=1 if data_array.shape[0] < 5000 else 0) # order to 0 for NN 
    nii = nib.Nifti1Image(data_array, mat)
    nii.header.set_data_dtype(np.int16)
    nii.header.set_zooms([outvox, outvox, outz])
    nib.save(nii, outnii)

def main(args):
    starttime = datetime.now()

    parser = parsefn()
    args = parser.parse_args()
    indir, d, outnii, vx, vz = args.folder, args.down, args.outnii, args.resx / 1000, args.resz / 1000

    ncpus = int(0.95 * multiprocessing.cpu_count())
    file_list = sorted(glob.glob(f"{indir}/*.tif*"), key=numericalsort)

    outdir = os.path.join(os.getcwd(), 'niftis')
    os.makedirs(outdir, exist_ok=True)

    memap = f'{outdir}/tmp_array_memmap.map'
    tif = cv2.imread(file_list[0], -1)
    tifx, tify = tif.shape
    tifxd, tifyd = int(round(tifx / d)), int(round(tify / d))

    newdata = np.memmap(memap, dtype=float, shape=(len(file_list), tifxd, tifyd), mode='w+')

    Parallel(n_jobs=ncpus, backend="threading")(
        delayed(converttiff2nii)(d, i, x, newdata, tifx) for i, x in enumerate(file_list))

    savenii(newdata, d, f'{outdir}/{outnii}.nii.gz', vx, vz)

    os.remove(memap)

    print(f"Conversion done in {(datetime.now() - starttime)}")

if __name__ == "__main__":
    main(sys.argv)
