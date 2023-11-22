import concurrent.futures #youtube.com/watch?v=fKl2JW_qrso
from datetime import datetime
import nibabel as nib
import numpy as np
import os
from pathlib import Path
import sys
import re ### ABC add

#Check if all outputs exist for each cluster and skip processing as relevant
cluster_cropped_output_list = []
bbox_output_list = []
cluster_volumes_output_list = []
seg_in_cluster_cropped_list = []

clusters = sys.argv[7:]

#### ABC add: determine whether to crop segmentation according to specific raters or consensus ####
segmentation = os.path.basename(sys.argv[6])
###match = re.search(r"([^_]+)_seg_ilastik_(\d+)$", segmentation)
match = re.search(r"([^_]+)_seg_ilastik_(\d+)\.nii\.gz$", segmentation)
if match:
    immuno_marker = match.group(1)
    rater = match.group(2)
    seg_type = f"{immuno_marker}_seg_ilastik_{rater}"
else:
    seg_type = f"consensus"
######

for i in clusters:
    #Define path/outputs:
    cluster_cropped_output = str(sys.argv[4]+'/clusters_cropped/crop_'+str(sys.argv[5])+'_native_cluster_'+str(i)+'.nii.gz')
    bbox_output = str(sys.argv[4]+'/bounding_boxes/bounding_box_'+str(sys.argv[5])+'_cluster_'+str(i)+'.txt')
    cluster_volumes_output = str(sys.argv[4]+'/cluster_volumes/'+str(sys.argv[5])+'_cluster_'+str(i)+'_volume_in_cubic_mm.txt')
    seg_in_cluster_cropped_output = str(sys.argv[4]+seg_type+'_cropped/3D_counts/crop_'+seg_type+'_'+str(sys.argv[5])+'_native_cluster_'+str(i)+'_3dc/crop_'+seg_type+'_'+str(sys.argv[5])+'_native_cluster_'+str(i)+'.nii.gz') ### ABC edit

    #add True or False to list depending on if outputs already exist:
    cluster_cropped_output_list.append(os.path.isfile(cluster_cropped_output))
    bbox_output_list.append(os.path.isfile(bbox_output))
    cluster_volumes_output_list.append(os.path.isfile(cluster_volumes_output))
    seg_in_cluster_cropped_list.append(os.path.isfile(seg_in_cluster_cropped_output))

if all(cluster_cropped_output_list) and all(bbox_output_list) and all(cluster_volumes_output_list) and all(seg_in_cluster_cropped_list): 
    print("  All outputs exist, skipping\n")
else:
    print(str('  Load cluster index and convert to ndarray '+datetime.now().strftime("%H:%M:%S")+'\n'))
    cluster_index_img = nib.load(sys.argv[1])
    cluster_index_ndarray = np.array(cluster_index_img.dataobj)

    #Make reference np.array lacking empty space around cluster index
    print(str('  Find bbox of cluster index and trim outer space '+datetime.now().strftime("%H:%M:%S")+'\n'))
    xy_view = np.any(cluster_index_ndarray, axis=2) #2D boolean array similar to max projection of z (True if > 0)
    outer_xmin = int(min(np.where(xy_view)[0])) #1st of 2 1D arrays of indices of True values
    outer_xmax = int(max(np.where(xy_view)[0])+1)
    outer_ymin = int(min(np.where(xy_view)[1]))
    outer_ymax = int(max(np.where(xy_view)[1])+1)
    yz_view = np.any(cluster_index_ndarray, axis=0)
    outer_zmin = int(min(np.where(yz_view)[1]))
    outer_zmax = int(max(np.where(yz_view)[1])+1)
    cluster_index_ndarray_cropped = cluster_index_ndarray[outer_xmin:outer_xmax, outer_ymin:outer_ymax, outer_zmin:outer_zmax] #Cropped cluster index
    with open(f"bounding_boxes/outer_bounds.txt", "w") as file:
        file.write(f"{outer_xmin}:{outer_xmax}, {outer_ymin}:{outer_ymax}, {outer_zmin}:{outer_zmax}")

    #Load cell segmentation .nii.gz
    print(str('  Load cell segmentation and trim outer space '+datetime.now().strftime("%H:%M:%S")+'\n'))
    seg_img = nib.load(sys.argv[6])
    seg_ndarray = np.array(seg_img.dataobj)
    seg_cropped = seg_ndarray[outer_xmin:outer_xmax, outer_ymin:outer_ymax, outer_zmin:outer_zmax] #Cropped cluster index
    seg_cropped = seg_cropped.squeeze() #removes single-dimensional elements from array 

def bbox_crop_vol(i):
    cluster_cropped_output = str(sys.argv[4]+'/clusters_cropped/crop_'+str(sys.argv[5])+'_native_cluster_'+str(i)+'.nii.gz')
    bbox_output = str(sys.argv[4]+'/bounding_boxes/bounding_box_'+str(sys.argv[5])+'_cluster_'+str(i)+'.txt')
    cluster_volumes_output = str(sys.argv[4]+'/cluster_volumes/'+str(sys.argv[5])+'_cluster_'+str(i)+'_volume_in_cubic_mm.txt')
    seg_in_cluster_cropped_output = str(sys.argv[4]+'/'+seg_type+'_cropped/3D_counts/crop_'+seg_type+'_'+str(sys.argv[5])+'_native_cluster_'+str(i)+'_3dc/crop_'+seg_type+'_'+str(sys.argv[5])+'_native_cluster_'+str(i)+'.nii.gz')  ### ABC edit

    if not os.path.isfile(cluster_cropped_output) or not os.path.isfile(bbox_output) or not os.path.isfile(cluster_volumes_output) or not os.path.isfile(seg_in_cluster_cropped_output):

        #Get bounding box for slicing/cropping each cluster from index: xmin:xmax,ymin:ymax,zmin:zmax
        if not os.path.isfile(cluster_cropped_output) or not os.path.isfile(seg_in_cluster_cropped_output):
            print(str(f'  Get cluster_{i} bbox '+datetime.now().strftime("%H:%M:%S")))
            index = np.where(cluster_index_ndarray_cropped == i) #1D arrays of indices of elements == i for each axis
            xmin = int(min(index[0]))
            xmax = int(max(index[0])+1)
            ymin = int(min(index[1]))
            ymax = int(max(index[1])+1)
            zmin = int(min(index[2])) 
            zmax = int(max(index[2])+1)
            with open(bbox_output, "w") as file:
                file.write(f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}")

        #Crop clusters, measure cluster volme, and save as seperate .nii.gz files
        if not os.path.isfile(cluster_cropped_output) or not os.path.isfile(seg_in_cluster_cropped_output):
            cluster_cropped = cluster_index_ndarray_cropped[xmin:xmax, ymin:ymax, zmin:zmax] #crop cluster
            cluster_cropped = cluster_cropped.squeeze()
        if not os.path.isfile(cluster_volumes_output):
            print(str(f'  Get cluster_{i} volume (mm^3) '+datetime.now().strftime("%H:%M:%S")))
            #((xy_res_in_um^2*)*xy_res_in_um)*ID_voxel_count/1000000000
            volume_in_cubic_mm = ((float(sys.argv[2])**2) * float(sys.argv[3])) * int(np.count_nonzero(cluster_cropped)) / 1000000000
            with open(cluster_volumes_output, "w") as file:
                file.write(f"{volume_in_cubic_mm}")
        if not os.path.isfile(cluster_cropped_output):
            print(str(f'  Save cluster_{i} cropped cluster mask '+datetime.now().strftime("%H:%M:%S")))
            image = np.where(cluster_cropped > 0, 1, 0).astype(np.uint8)
            image = nib.Nifti1Image(image, np.eye(4))
            nib.save(image, cluster_cropped_output)

        #Crop seg_in_clusters and save as seperate .nii.gz files
        if not os.path.isfile(seg_in_cluster_cropped_output):
            print(str(f"  Crop cluster_{i} cell segmentation, zero out voxels outside of cluster, & save "+datetime.now().strftime("%H:%M:%S")))
            seg_cluster_cropped = seg_cropped[xmin:xmax, ymin:ymax, zmin:zmax]
            cluster_cropped = np.where(cluster_cropped == i, 1, 0)
            cluster_cropped = cluster_cropped.astype(np.uint8)
            seg_in_cluster_cropped = cluster_cropped * seg_cluster_cropped #zero out segmented cells outside of clusters
            image = np.where(seg_in_cluster_cropped > 0, 1, 0).astype(np.uint8)
            image = nib.Nifti1Image(image, np.eye(4))
            Path(str(sys.argv[4]+'/'+seg_type+'_cropped/3D_counts/crop_'+seg_type+'_'+str(sys.argv[5])+'_native_cluster_'+str(i)+'_3dc')).mkdir(parents=True, exist_ok=True) #ABC edit
            nib.save(image, seg_in_cluster_cropped_output)

if not all(cluster_cropped_output_list) or not all(bbox_output_list) or not all(cluster_volumes_output_list) or not all(seg_in_cluster_cropped_list): 
    clusters = list(map(int, clusters)) #convert to ints
    with concurrent.futures.ProcessPoolExecutor() as executor:
        executor.map(bbox_crop_vol, clusters)
    print(str("  Finished native_clusters_any_immunofluor_rater_abc.py "+datetime.now().strftime("%H:%M:%S")+'\n'))

#Daniel Ryskamp Rijsketic 11/11/22 11/22-23/22 12/9-15/22 (Heifets lab)
#Austen Brooks Casey 7/13/23 (Heifets Lab) modified to be more flexible in accepting and outputting cropped consensus or rater-specici ilastik segmentations 
