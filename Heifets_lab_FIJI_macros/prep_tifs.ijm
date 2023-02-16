// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
setBatchMode(true);

inputlist=getArgument();
input=split(inputlist,'#');

//************ Open image sequence *************************************************
run("Image Sequence...", "open=["+input[0]+"] sort"); // path/1st_tif
dir=getDirectory("image");
ParentFolderPath=File.getParent(dir);
sample=File.getName(ParentFolderPath);

getDimensions(width, height, channels, slices, frames);

if (input[2]=="SizeX_odd") {
  width=width-1;
} 

if (input[3]=="SizeY_odd") {
  height=height-1;
}

makeRectangle(0, 0, width, height);
run("Crop");

if (input[1]=="0") {
  run("Image Sequence... ", "dir="+ParentFolderPath+"/"+input[4]+"/ format=TIFF name="+sample+input[5]);
}  else {
  //************ Adjust display range ****************************************************
  setMinAndMax(input[1], 65535); //input[1] = 488 min passed from prep_tifs.sh 
  run("Apply LUT", "stack");
  run("Image Sequence... ", "dir="+ParentFolderPath+"/"+input[4]+"/ format=TIFF name="+sample+input[5]);
  close();

  //************ Save 488_min to log it and prevent reprocessing *************************
  print(input[1]);
  selectWindow("Log");
  saveAs("Text", "["+ParentFolderPath+"/parameters/488_min]");
}

setBatchMode(false);

run("Quit");


//Daniel Rijsketic 6/20/21 & 6/8/22 & 7/7/22 & 7/18/22 (Heifets lab)
