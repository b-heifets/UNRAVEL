// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

setBatchMode(true); 

filelist = getArgument();
file = split(filelist,'#');
run("Image Sequence...", "open=["+file[0]+"] sort"); //select first 488 folder
dir = getDirectory("image");
image = getTitle();

X = getWidth();
Y = getHeight();
Z = nSlices;

//2x downsampled dimensions
dsX = round(X/2);
dsY = round(Y/2);
dsZ = round(Z/2);

run("Scale...", "x=.5 y=.5 z=.5 width="+dsX+" height="+dsY+" depth="+dsZ+" interpolation=Bilinear process create");

run("NIfTI-1", "save="+dir+"/2xDS_488.nii");
//saveAs("Tiff", dir+"2xDS_488");

setBatchMode(false); 
run("Quit");


//Daniel Ryskamp Rijsketic 07/12/22 (Heifets Lab)
