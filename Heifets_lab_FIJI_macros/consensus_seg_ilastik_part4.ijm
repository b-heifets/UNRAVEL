// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// seg_consensus (Daniel Rijsketic Jan. 17, 2022; Heifets lab)
//===================================================

//Inputs: 1) seg_ilastik_XX/seg_ilastik.tif
//Outputs: sampleX/consensus/consensus.tif

//setBatchMode(true); 

filelist = getArgument();
file = split(filelist,'#');

//Convert background (255 to 1)
function binarize() {
run("Out [-]");
run("Out [-]");
setThreshold(255, 255);
for (i = 1; i <= nSlices; i++) { 
setSlice(i); 
getStatistics(area, mean, min, max, std, histogram);
if (max>0) {
run("Create Selection"); 
run("Set...", "value=1");
run("Select None");
}
} 
resetThreshold;
}

//************ Open seg_ilastik_XX/seg_ilastik.tif *******************************************
open(file[0]);
rename("seg_ilastik_5.tif");
binarize();

Dir = getDirectory("image"); 
Sample_Dir=File.getParent(Dir);
sample=File.getName(Sample_Dir);
consensusDir= Sample_Dir + "/consensus/";

open(consensusDir+"Result_of_seg_ilastik_4.tif");
imageCalculator("Add create stack", "seg_ilastik_5.tif","Result_of_seg_ilastik_4.tif");

//If pixel has value of 3 or more it will be included in the mask (pixels preserved as cells if segmented by 3/5 raters)
setThreshold(0, 2);
run("Convert to Mask", "method=Default background=Dark black");
run("Invert", "stack");
//saveAs("Tiff", consensusDir+"consensus");
run("NIfTI-1", "save="+consensusDir+sample+"_consensus.nii");

run("Close All");

setBatchMode(false);

run("Quit");

