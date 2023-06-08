// adjust_dr.ijm (Daniel Rijsketic Jan. 06, 2022; Heifets lab)
//===================================================

setBatchMode(true);

inputlist=getArgument();
input=split(inputlist,'#');

run("Image Sequence...", "open=["+input[0]+"] sort"); //select first image in 488 folder
dir=getDirectory("image");
ParentFolderPath=File.getParent(dir);
sample=File.getName(ParentFolderPath);
image=getTitle();

setMinAndMax(input[1], input[2]);
run("Apply LUT", "stack");

//run("Image Sequence... ", "format=TIFF save="+dir+"ch03_0000.tif");
//run("Image Sequence... ", "format=TIFF name=ch3_ save="+dir+"/488/"+SampleFolder+"_Ch1_0000.tif");
run("Image Sequence... ", "format=TIFF name="+sample+"_Ch1_ save="+dir);

setBatchMode(false);
run("Quit");
