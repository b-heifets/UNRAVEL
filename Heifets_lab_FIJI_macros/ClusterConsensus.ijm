// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// ClusterConsensus (Daniel Rijsketic May 17, 2022; Heifets lab)
//===================================================

setBatchMode(true);

inputlist = getArgument();
input = split(inputlist,'#');

//open cropped cluster////////////////////////////////////////
open(input[0]); 
cluster = getTitle()

//open cropped consensus ////////////////////////////////////////
open(input[1]); 
consensus = getTitle()

//zero out cells outside of cluster
imageCalculator("Multiply create 32-bit stack", cluster, consensus);
ClusterConsensus=getTitle();
setOption("ScaleConversions", false);
run("16-bit");

run("NIfTI-1", "save="+input[2]+"/"+consensus+".nii");

setBatchMode(false);

run("Quit");


