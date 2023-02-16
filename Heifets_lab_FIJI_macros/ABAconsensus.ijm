// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// ABAconsensus (Daniel Rijsketic June 17, 2022)
//===================================================

//opens $PWD/reg_final/"$sample"_native_gubra_ano_split.nii.gz#$PWD/consensus/"$sample"_consensus.tif and converts consensus into ABA intesity values

setBatchMode(true); 

filelist = getArgument();
file = split(filelist,'#');

//************ 1) Open "$sample"_native_gubra_ano_split.nii.gz ***********************************************************************
open(file[0]);
ABA=getTitle();

//************ 2) Open "$sample"_consensus.tif ************************************************
open(file[1]); 
dir=getDirectory("image");
ParentFolderPath=File.getParent(dir);
sample=File.getName(ParentFolderPath);
consensus=getTitle();

//convert consensus into ABA intensity values
selectWindow(consensus); 
imageCalculator("Divide create 32-bit stack", consensus, consensus);
consensus_divided=getTitle();
selectWindow(consensus);
close();
imageCalculator("Multiply create 32-bit stack", ABA, consensus_divided);
ABAconsensus=getTitle();
selectWindow(ABA);
close();
selectWindow(consensus_divided)
close(); 
selectWindow(ABAconsensus); 
setOption("ScaleConversions", false);
run("16-bit"); 

//Save native full res 
run("NIfTI-1", "save="+dir+sample+"_ABAconsensus.nii");

setBatchMode(false);

run("Quit");


