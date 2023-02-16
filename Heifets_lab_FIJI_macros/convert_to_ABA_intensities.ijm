// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// convert_to_ABA_intensities (Daniel Rijsketic June 17, 2022; Heifets lab)
//===================================================

setBatchMode(true); 

filelist = getArgument();
file = split(filelist,'#');

//************ 1) Open "$sample"_native_gubra_ano_split.nii.gz ***********************************************************************
open(file[0]);
ABA=getTitle();

//************ 2) Open image to convert ************************************************
open(file[1]); 
dir=getDirectory("image");
ParentFolderPath=File.getParent(dir);
sample=File.getName(ParentFolderPath);
image=getTitle();

//convert image into ABA intensity values
selectWindow(image); 
imageCalculator("Divide create 32-bit stack", image, image);
image_divided=getTitle();
selectWindow(image);
close();
imageCalculator("Multiply create 32-bit stack", ABA, image_divided);
ABAimage=getTitle();
selectWindow(ABA);
close();
selectWindow(image_divided)
close(); 
selectWindow(ABAimage); 
setOption("ScaleConversions", false);
run("16-bit"); 

//Save native full res 
run("NIfTI-1", "save="+dir+image+".nii");

setBatchMode(false);

run("Quit");


