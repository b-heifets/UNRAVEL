// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// integrated_densities_for_stack (Daniel Rijsketic May 31, 2022; Heifets lab)
//===================================================
 
setBatchMode(true);

filelist = getArgument();
file = split(filelist,'#');

//open cropped image////////////////////////////////////////
open(file[0]); 
image = getTitle()
dir = getDirectory("image");

run("Set Measurements...", "integrated redirect=None decimal=3");
for (i=1; i<nSlices+1;i++) {
  Stack.setSlice(i); 	
  run("Measure");
};

saveAs("Results", dir+image+"_IntDen.csv");

setBatchMode(false);

run("Quit");



