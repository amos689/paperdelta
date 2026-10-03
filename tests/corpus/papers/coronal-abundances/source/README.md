# Modeling Time-Variable Elemental Abundances in Coronal Loop Simulations

A paper by Jeffrey Reep, John Unverferth, Will Barnes, and Sherry Chhabra describing a method to add time-variable elemental abundances due to chromospheric evaporation into coronal loop simulations.  An up-to-date preprint is available on the `main-pdf` branch of this repository.  

In order to compile this paper, 

(1) Install the ebtel++ code (https://github.com/rice-solar-physics/ebtelPlusPlus).  

(2) Build ebtel++ by running `scons` at the command line

(3) Define a system variable $EBTELPLUSPLUS_DIR to point to the local installation of ebtel++

(4) Install the `showyourwork` package (preferably in its own conda environment)

(5) From the main directory, type `showyourwork build`

This paper was produced with version 0.2 of ebtel++ (https://zenodo.org/records/12675386), and the data to produce the figures has been cached on Zenodo (https://zenodo.org/records/12695938).  


<p align="center">
<a href="https://github.com/showyourwork/showyourwork">
<img width = "450" src="https://raw.githubusercontent.com/showyourwork/.github/main/images/showyourwork.png" alt="showyourwork"/>
</a>
<br>
<br>
<a href="https://github.com/jwreep/ebtel_abundances/actions/workflows/build.yml">
<img src="https://github.com/jwreep/ebtel_abundances/actions/workflows/build.yml/badge.svg?branch=main" alt="Article status"/>
</a>
<a href="https://github.com/jwreep/ebtel_abundances/raw/main-pdf/arxiv.tar.gz">
<img src="https://img.shields.io/badge/article-tarball-blue.svg?style=flat" alt="Article tarball"/>
</a>
<a href="https://github.com/jwreep/ebtel_abundances/raw/main-pdf/ms.pdf">
<img src="https://img.shields.io/badge/article-pdf-blue.svg?style=flat" alt="Read the article"/>
</a>
</p>

An open source scientific article created using the [showyourwork](https://github.com/showyourwork/showyourwork) workflow.
