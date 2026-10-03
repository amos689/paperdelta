# On the Estimation of Centre of Mass in Periodic Systems

<p align="justify">
Calculation of the centre of mass of a group of particles in a periodically-repeating cell is an important aspect of chemical and physical simulation. 
One popular approach calculates the centre of mass via the projection of the individual particles' coordinates onto a circle [Bai & Breen, <i>J. Graph. Tools</i>, <b>13</b>(4), 53, (2008)].
However, this approach involves averaging of the particles in a non-physically meaningful way resulting in inaccurate centres of mass. 
Instead the intrinsic weighted average should be computed, but the analytical calculation of this is computationally expensive and complex. 
Here, we propose a more computationally efficient approach to compute the intrinsic mean that is suitable for the majority of chemical systems. 
</p>

---
<p align="center">
<a href="https://github.com/scams-research/centre-of-mass/actions/workflows/build.yml">
<img src="https://github.com/scams-research/centre-of-mass/actions/workflows/build.yml/badge.svg" alt="Article status"/>
</a>
<a href="https://github.com/scams-research/centre-of-mass/raw/main-pdf/arxiv.tar.gz">
<img src="https://img.shields.io/badge/article-tarball-blue.svg?style=flat" alt="Article tarball"/>
</a>
<a href="https://github.com/scams-research/centre-of-mass/raw/main-pdf/ms.pdf">
<img src="https://img.shields.io/badge/article-pdf-blue.svg?style=flat" alt="Read the article"/>
</a>
<a href="https://arxiv.org/abs/2501.14578">
<img src="https://img.shields.io/badge/arXiv-2501.14578-orange.svg"/>
</a>
<a href="https://doi.org/10.1063/5.0260928">
<img src="https://img.shields.io/badge/publication%20DOI-10.1063/5.0260928-yellow.svg?style=flat"/>
</a>
<br><br>
<a href= "https://orcid.org/0009-0002-6808-4573">Harry Richardson</a>,
<a href="https://orcid.org/0000-0003-2659-0806">Josh Dunn</a>,
and 
<a href="https://orcid.org/0000-0003-3381-5911">Andrew R. McCluskey</a>&ast;<br>
&ast;<a href="mailto:andrew.mccluskey@bristol.ac.uk">andrew.mccluskey@bristol.ac.uk</a>
</p>

---

This is the electronic supplementary information (ESI) associated with the publication "On the Estimation of Centre of Mass in Periodic Systems". 
This ESI uses [`showyourwork`](https://show-your.work) to provide a completely reproducible and automated analysis, plotting, and paper generation workflow. 
To run the workflow and generate the paper locally using the cached data run the following: 
```
git clone git@github.com:scams-research/centre-of-mass.git
cd centre-of-mass
pip install showyourwork
showyourwork build 
```
Full details of the workflow can be determined from the [`Snakefile`](https://github.com/scams-research/centre-of-mass/blob/main/Snakefile) and the [`showyourwork.yml`](https://github.com/scams-research/centre-of-mass/blob/main/showyourwork.yml).
