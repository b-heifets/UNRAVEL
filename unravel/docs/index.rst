.. UNRAVEL documentation master file, created by
   sphinx-quickstart on Tue Jun  4 17:52:09 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.
   
.. raw:: html

    <a href="https://github.com/b-heifets/UNRAVEL/tree/main" target="_blank">
        <img id="unravel-logo" src="_static/UNRAVEL_logo.png" alt="UNRAVEL Logo" class="custom-logo" style="background-color: transparent;">
    </a>

.. raw:: html

    <style>
        video {
            border: none;
            outline: none;
        }
    </style>

    <div style="display: flex; justify-content: space-between;">
        <div style="flex: 1; margin-right: 10px;">
            <a href="https://www.nature.com/articles/s41386-023-01613-4" target="_blank">
                <video width="100%" autoplay muted playsinline>
                  <source src="_static/psilocybin_up_valid_clusters.mp4" type="video/mp4">
                  Your browser does not support the video tag.
                </video>
            </a>
        </div>
        <div style="flex: 1; margin-left: 10px;">
            <a href="https://www.nature.com/articles/s41386-023-01613-4" target="_blank">
                <video width="100%" autoplay muted playsinline>
                  <source src="_static/psilocybin_up_sunburst.mp4" type="video/mp4">
                  Your browser does not support the video tag.
                </video>
            </a>
        </div>
    </div>
    
.. raw:: html

    <br>

UN-biased high-Resolution Analysis and Validation of Ensembles using Light sheet images
=======================================================================================
* UNRAVEL is a `Python <https://www.python.org/>`_ package & command line tool for the analysis of brain-wide imaging data, automating: 
    * Registration of brain-wide images to a common atlas space
    * Quantification of cell/label densities across the brain
    * Voxel-wise analysis of fluorescent signals and cluster correction
    * Validation of hot/cold spots via cell/label density quantification at cellular resolution
* `UNRAVEL GitHub repository <https://github.com/b-heifets/UNRAVEL/tree/main>`_
* `UNRAVEL can be installed via the Python Package Index (PyPI) <https://pypi.org/project/heifetslab-unravel/>`_ with this command:
  .. code-block:: bash
      pip install heifetslab-unravel
* `Initial UNRAVEL publication <https://www.nature.com/articles/s41386-023-01613-4>`_
* UNRAVEL was developed by `the Heifets lab <https://heifetslab.stanford.edu/>`_ and `TensorAnalytics <https://sites.google.com/view/tensoranalytics/home?authuser=0>`_
* Additional support/guidance was provided by:
    * `The Shamloo lab <https://med.stanford.edu/neurosurgery/research/shamloo.html>`_
    * `The Malenka lab <https://profiles.stanford.edu/robert-malenka>`_
    * `The Stanford-based P50 center funded by NIDA <https://med.stanford.edu/nidap50.html>`_

.. raw:: html

    <br>

.. raw:: html

    <div style="text-align: center;">
        <a href="https://heifetslab.stanford.edu/" target="_blank">
            <img id="heifets-logo" src="_static/Heifets_lab_logo.png" alt="Heifets Lab">
        </a>
    </div>

Getting started
---------------
* `Guide on immunofluorescence staining, iDISCO+, & lightsheet fluorescence microscopy <https://docs.google.com/document/d/16yowBhiBQWz8_VX2t9Rf6Xo3Ub4YPYD6qeJP6vJo6P4/edit?usp=sharing>`_
* :doc:`installation`
* :doc:`guide`
* :doc:`unravel/toc`


UNRAVEL visualizer
-------------------
* `UNRAVEL visualizer <https://heifetslab-unravel.org/>`_ is a web-based tool for visualizing and exploring 3D maps output from UNRAVEL
* `UNRAVEL visualizer GitHub repo <https://github.com/MetaCell/cfos-visualizer/>`_
* Developed by `MetaCell <https://metacell.us/>`_ with support from the `Heifets lab <https://heifetslab.stanford.edu/>`_

.. raw:: html

    <div style="text-align: center;">
        <a href="https://heifetslab-unravel.org/" target="_blank">
            <img id="unravel-visualizer" src="_static/UNRAVEL_visualizer.png" alt="UNRAVEL visualizer">
        </a>
    </div>


Contact us
----------
If you have any questions, suggestions, or are interested in collaborations and contributions, please reach out to us. 


Developers
----------
* **Daniel Ryskamp Rijsketic** (developer and maintainer) - `danrijs@stanford.edu <mailto:danrijs@stanford.edu>`_
* **Austen Casey** (developer) - `abcasey@stanford.edu <mailto:abcasey@stanford.edu>`_
* **MetaCell** (UNRAVEL visualizer developers) - `info@metacell.us <info@metacell.us>`_
* **Boris Heifets** (PI) - `bheifets@stanford.edu <mailto:bheifets@stanford.edu>`_


Additional contributions from
-----------------------------
* **Mehrdad Shamloo** (PI) - `shamloo@stanford.edu <mailto:shamloo@stanford.edu>`_
* **Daniel Barbosa** (early contributer and guidance) - `Dbarbosa@pennmedicine.upenn.edu <mailto:Dbarbosa@pennmedicine.upenn.edu>`_
* **Wesley Zhao** (guidance) - `weszhao@stanford.edu <mailto:weszhao@stanford.edu>`_
* **Nick Gregory** (guidance) - `ngregory@stanford.edu <mailto:ngregory@stanford.edu>`_


Main dependencies
-----------------
* `Allen Institute for Brain Science <https://portal.brain-map.org/>`_
* `FSL <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki>`_
* `fslpy <https://git.fmrib.ox.ac.uk/fsl/fslpy>`_
* `ANTsPy <https://github.com/ANTsX/ANTsPy>`_
* `Ilastik <https://www.ilastik.org/>`_
* `nibabel <https://nipy.org/nibabel/>`_
* `numpy <https://numpy.org/>`_
* `scipy <https://www.scipy.org/>`_
* `pandas <https://pandas.pydata.org/>`_
* `cc3d <https://pypi.org/project/connected-components-3d/>`_
* Registration and warping workflows were inspired by `MIRACL <https://miracl.readthedocs.io/en/latest/>`_
* We warped this `LSFM/iDISCO+ average template brain <https://pubmed.ncbi.nlm.nih.gov/33063286/>`_ to Allen brain atlas space (CCFv3) and refined alignment. 

Support is welcome for
----------------------
* Analysis of new datasets
* Development of new features
* Maintenance of the codebase
* Guidance of new users

.. raw:: html

    <br>

.. toctree::
   :maxdepth: 4
   :caption: Contents:

   installation
   guide
   unravel/toc

.. raw:: html

    <br>


Indices
=======

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`



.. raw:: html

    <script>
        document.getElementById('video1').addEventListener('ended', function() {
            this.controls = false;
        });
        document.getElementById('video2').addEventListener('ended', function() {
            this.controls = false;
        });
    </script>