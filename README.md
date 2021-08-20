# GEOGEAR

contact: timlenters@gmail.com

## Introduction
GEOGEAR provides a method for creating integrated data products from disparate geospatial layers. It provides the following features:

1. Enabling users to interactively configure and customize data products for differ-ent applications from data of different formats, resolutions and projections through a notebook-based easy-to-use user interface, which provides multiple spatial analysis functions, automatically harmonizes input data and doesn’t re-quire extensive programming knowledge to use.
2. Optimizing computing performance through automated workflow scheduling and parallelization of compute-intensive steps.
3. Automating the collection of dynamic contextual information through generat-ing provenance records which follow PROV-O and ISO-19115 metadata stand-ards. This promotes the reproducibility, re-use and interoperability of data prod-ucts.

This repository contains the following Python and Jupyter notebook files used by GEOGEAR:

* `backend.py`: This script holds the `analysis()` function that is called when the analysis is started. It determines the workflow logic and merges provenance documents.
* `functions.py`: This script holds the three analysis functions currently implemented in GEOGEAR (`coverages`,`presence_absence` and `resample`), functions to download spatial layers and generate grids.
* `ui.ipynb`: This Jupyter notebook contains the user interface of GEOGEAR. All interactions can be done through the widgets, coding is only required when customizing. How-to-use is explained in the notebook.

# How to install
GEOGEAR is currently optimized to use on Unix-systems. Windows requires manual installation of `geopandas` and its dependencies ([link](https://towardsdatascience.com/geopandas-installation-the-easy-way-for-windows-31a666b3610f))

The current release of GEOGEAR can be download through pip: `pip install geogear`. This contains the `.py` files from this directory and installs Python dependencies.

The current implementation of GEOGEAR relies on separate installations of SAGA GIS (v. 7.7.0) and GDAL (v. 3.0.4) which can be downloaded from https://sourceforge.net/projects/saga-gis/ and https://gdal.org/download.html, re-spectively. When on windows, the `saga_cmd` variable has to be set manually to the path containing your SAGA GIS installation.