# UNRAVEL
#### UN-biased high-Resolution Analysis and Validation of Ensembles using Light sheet images 

---

### *Please see [UNRAVEL 1.0.0-beta](https://github.com/b-heifets/UNRAVEL/tree/dev) for the latest code and [UNRAVEL documentation](https://b-heifets.github.io/UNRAVEL/) for guides on [installation](https://b-heifets.github.io/UNRAVEL/installation.html) and [anaysis](https://b-heifets.github.io/UNRAVEL/guide.html)*

---

\
UNRAVEL is a command line tool for:
* Voxel-wise analysis of fluorescent signals (e.g., c-Fos immunofluorescence) across the mouse brains in atlas space
* Validation of hot/cold spots via c-Fos+ cell density quantification and montages at cellular resolution

\
Publications: 
* UNRAVELing the synergistic effects of psilocybin and environment on brain-wide immediate early gene expression in mice 
    * [Neuropsychopharmacology](https://www.nature.com/articles/s41386-023-01613-4)
    * [bioRxiv](https://www.biorxiv.org/content/10.1101/2023.02.19.528997v1)

\
[UNRAVEL guide:](https://office365stanford-my.sharepoint.com/:p:/g/personal/danrijs_stanford_edu/EbQN54e7SwRHgkmw3yn8fgcBz1xG22AICtZx8nsPrOLFtg?e=S159PM)
* Notes dependencies, paths to update, organization of files/folders, and info on running scripts:
* Key scripts: find_clusters.sh, glm.sh, and validate_clusters2.sh
* Scripts can be run in a modular fashion:
    * overview.sh -> prep_tifs.sh or czi_to_tif.sh -> 488_to_nii.sh -> reg.sh -> rb.sh -> z_brain_template_mask.sh -> glm.sh -> validate_clusters2.sh 
* Scripts start with a help guide. View by running: <script>.sh help

\
For command line interface help, please review [Unix tutorials](https://andysbrainbook.readthedocs.io/en/latest/index.html)

\
[Heifets lab guide to immunofluorescence staining, iDISCO+, & lightsheet fluorescence microscopy](https://docs.google.com/document/d/16yowBhiBQWz8_VX2t9Rf6Xo3Ub4YPYD6qeJP6vJo6P4/edit?usp=sharing)

\
Please send questions/suggestions to:
* Daniel Ryskamp Rijsketic (danrijs@stanford.edu)
* Austen Casey (abcasey@stanford.edu)
* Boris Heifets (bheifets@stanford.edu)
