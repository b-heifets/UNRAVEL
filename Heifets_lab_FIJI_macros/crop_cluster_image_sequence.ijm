// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// crop_cluster_image_sequence (Daniel Rijsketic May 5, 2022)
//==========================================================
//crops roi in 3D
//Inputs: 1) stack to process (single tif or .nii.gz) and 2) bounding box of roi
//Outputs: input file cropped 
//get bounding box with: fslstats <input> -w #outputs smallest ROI <xmin> <xsize> <ymin> <ysize> <zmin> <zsize> <tmin> <tsize> containing nonzero voxels

//Run:
// /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro crop_roi <./image.tif>#<xmin>#<xsize>#<ymin>#<ysize>#<zmin>#<zsize>

setBatchMode(true);

// Input data
inputlist = getArgument();
input = split(inputlist,'#');
run("Image Sequence...", "open=["+input[0]+"] sort") // select first image of sequence 
dir = getDirectory("image");
input_image = getTitle();

//xy crop (xmin, ymin, xsize, ysize)
xmin=input[1];
xsize=input[2];
ymin=input[3];
ysize=input[4];
makeRectangle(xmin, ymin, xsize, ysize);

//z crop
zmin_plus_one=input[5];
zmax=input[6];
run("Duplicate...", "duplicate range="+zmin_plus_one+"-"+zmax+"");
cropped_roi = getTitle();

run("NIfTI-1", "save="+input[7]+"/crop_"+input_image+".nii");

setBatchMode(false);

run("Quit");

