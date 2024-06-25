[![UNRAVEL Logo](https://raw.githubusercontent.com/b-heifets/UNRAVEL/main/unravel/docs/_static/UNRAVEL_logo.png)](https://b-heifets.github.io/UNRAVEL/)

### UN-biased high-Resolution Analysis and Validation of Ensembles using Light sheet images
* UNRAVEL is a [Python](https://www.python.org/) package & command line tool for the analysis of brain-wide imaging data, automating: 
    * Registration of brain-wide images to a common atlas space
    * Quantification of cell/label densities across the brain
    * Voxel-wise analysis of fluorescent signals and cluster correction
    * Validation of hot/cold spots via cell/label density quantification at cellular resolution
* [Initial UNRAVEL publication](https://www.nature.com/articles/s41386-023-01613-4)
* UNRAVEL was developed by [the Heifets lab](https://heifetslab.stanford.edu/) and [TensorAnalytics](https://sites.google.com/view/tensoranalytics/home?authuser=0)
* Additional support/guidance was provided by: 
    * [The Shamloo lab](https://med.stanford.edu/neurosurgery/research/shamloo.html)
    * [The Malenka lab](https://profiles.stanford.edu/robert-malenka)
    * [The Stanford-based P50 center funded by NIDA](https://med.stanford.edu/nidap50.html)

---

### *Please see [UNRAVEL documentation](https://b-heifets.github.io/UNRAVEL/) for guides on [installation](https://b-heifets.github.io/UNRAVEL/installation.html) and [analysis](https://b-heifets.github.io/UNRAVEL/guide.html)*

---

[<img src="https://raw.githubusercontent.com/b-heifets/UNRAVEL/main/unravel/docs/_static/Heifets_lab_logo.png" alt="Heifets Lab" width="500">](https://heifetslab.stanford.edu/)




### UNRAVEL visualizer
* [UNRAVEL visualizer](https://heifetslab-unravel.org/) is a web-based tool for visualizing and exploring 3D maps output from UNRAVEL
* [UNRAVEL visualizer GitHub repo](https://github.com/MetaCell/cfos-visualizer/)
* Developed by [MetaCell](https://metacell.us/) with support from the [Heifets lab](https://heifetslab.stanford.edu/)

[![UNRAVEL visualizer](https://raw.githubusercontent.com/b-heifets/UNRAVEL/main/unravel/docs/_static/UNRAVEL_visualizer.png)](https://heifetslab-unravel.org/)

### Contact us
If you have any questions, suggestions, or are interested in collaborations and contributions, please reach out to us. 

### Developers
* **Daniel Ryskamp Rijsketic** (lead developer and maintainer) - [danrijs@stanford.edu](mailto:danrijs@stanford.edu)
* **Austen Casey** (developer) - [abcasey@stanford.edu](mailto:abcasey@stanford.edu)
* **MetaCell** (UNRAVEL visualizer developers) - [info@metacell.us](mailto:info@metacell.us)
* **Boris Heifets** (PI) - [bheifets@stanford.edu](mailto:bheifets@stanford.edu)

### Additional contributions from
* **Mehrdad Shamloo** (PI) - [shamloo@stanford.edu](mailto:shamloo@stanford.edu)
* **Daniel Barbosa** (early contributer and guidance) - [Dbarbosa@pennmedicine.upenn.edu](mailto:Dbarbosa@pennmedicine.upenn.edu)
* **Wesley Zhao** (guidance) - [weszhao@stanford.edu](mailto:weszhao@stanford.edu)
* **Nick Gregory** (guidance) - [ngregory@stanford.edu](mailto:ngregory@stanford.edu)

### Main dependencies
* [Allen Institute for Brain Science](https://portal.brain-map.org/)
* [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki)
* [fslpy](https://git.fmrib.ox.ac.uk/fsl/fslpy)
* [ANTsPy](https://github.com/ANTsX/ANTsPy)
* [Ilastik](https://www.ilastik.org/)
* [nibabel](https://nipy.org/nibabel/)
* [numpy](https://numpy.org/)
* [scipy](https://www.scipy.org/)
* [pandas](https://pandas.pydata.org/)
* [cc3d](https://pypi.org/project/connected-components-3d/)
* Registration and warping workflows were inspired by [MIRACL](https://miracl.readthedocs.io/en/latest/)
* We adapted [LSFM/iDISCO+ atlases](https://pubmed.ncbi.nlm.nih.gov/33063286/) from [Gubra](https://www.gubra.dk/cro-services/3d-imaging/)

### Support is welcome for
* Analysis of new datasets
* Development of new features
* Maintenance of the codebase
* Guidance of new users