// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
// ABAconsensus_25sliceSubstacks (Daniel Rijsketic 09/28/21 & 09/22/22 )
//===================================================

//Splits sampleX_ABAconsensus.nii.gz into ~25 slice substacks for 3D object counting on the GPU

//Inputs: 1) sample??/consensus/sampleX_ABAconsensus.nii.gz 
//Outputs: substacks in /consensus/ABAconsensus_stacks_25slices/

//To run:
//open terminal from sample folder, . activate miracl, ABAconsensus_3dc.sh

setBatchMode(true);

filelist = getArgument();
file = split(filelist,'#');

open(file[0]); //Open consensus/sampleX_ABAconsensus.nii.gz
dir = getDirectory("image");
ABAconsensusZ=nSlices;

//Save as substacks (with 1 pixel overlap for alternating between exclude pixels on edges and include pixels on egdes during the 3D object counting on GPU)
splitDir= dir + "/ABAconsensus_stacks_25slices/";
File.makeDirectory(splitDir);
//27e 25i (aka 25 slices; e = stacks excluding objects on edges; i = stacks including objects on edges)
NumberOfABAsegSubstacks=-floor(-ABAconsensusZ/50); //rounds up 
for (i = 1; i < NumberOfABAsegSubstacks + 1; i++) {
  a = (50*i-49);  //1-27 	   51-77
  b = (a+26);
  run("Duplicate...", "duplicate range="+a+"-"+b);
  saveAs("Tiff", splitDir+"ABAconsensus_"+a+"_"+b+"_ExcludeEdges");
  close();
};
NumberOfABAsegSubstacks=floor(ABAconsensusZ/50); //changed round to floor to round down
for (i = 1; i < NumberOfABAsegSubstacks + 1; i++) {
  a = (50*i-49);
  b = (a+26);
  c = b+24;            //27-51    77-101
  run("Duplicate...", "duplicate range="+b+"-"+c);
  saveAs("Tiff", splitDir+"ABAconsensus_"+b+"_"+c+"_IncludeEdges");
  close();
};
close();

setBatchMode(false);
run("Quit");


