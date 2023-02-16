// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
setBatchMode(true); 

inputlist = getArgument();
input = split(inputlist,'#');

//************ Open ochann image sequence**********************************************
run("Image Sequence...", "open=["+input[0]+"] sort");
dir = getDirectory("image");
ParentFolderPath=File.getParent(dir);
sample=File.getName(ParentFolderPath);

run("Subtract Background...", "rolling="+input[1]+" stack");

run("Image Sequence... ", "format=TIFF name="+sample+"_Ch2_rb"+input[1]+"_ save="+ParentFolderPath+"/ochann_rb"+input[1]+"/"+sample+"_Ch2_rb"+input[1]+"_0000.tif");

setBatchMode(false);

run("Quit");

//Daniel Ryskamp Rijsketic 12/02/21 (Heifets Lab)
