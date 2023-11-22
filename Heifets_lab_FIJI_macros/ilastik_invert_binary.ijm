//Script used to convert ilastik segmentation to binary imagess 
//Inputs: 1) Ilastik sementation tif series for 1 raters 
//Outputs:a single rater binary ilastik segmentation file 

setBatchMode(true); 

filelist = getArgument();
file = split(filelist,'#');

//Convert background (label 2, so intensity 2) to 0
run("Image Sequence...", "open=["+file[0]+"] sort"); // select first segmentation tif in series
dir = getDirectory("image");
selectWindow("IlastikSegmentation");
HotPix = 2;  
Stack.getStatistics(voxelCount, mean, min, StackMax, stdDev); 
setThreshold(HotPix, StackMax); 
for (i = 1; i <= nSlices; i++) { 
 setSlice(i);
 label = getInfo("slice.label");
 run("Create Selection"); 
  if (selectionType() != 1) { 
  run("Set...", "value=0"); } 
  run("Select None"); } 
  resetThreshold;
run("Image Sequence... ", "format=TIFF use save="+dir+"");


run("Close All");

setBatchMode(false);

run("Quit");

