# credits

made by **Jnaor**

discord: **jake_5101** :D

## the stuff this uses

| thing | who made it | what it does |
| --- | --- | --- |
| [Transit Least Squares](https://github.com/hippke/tls) | Michael Hippke, René Heller, and contributors | The reference transit-search engine. The app currently uses TLS 1.32. |
| [batman](https://lkreidberg.github.io/batman/docs/html/index.html) | Laura Kreidberg and contributors | Physical transit templates inside TLS 1.32; also used for the app's injection tests. |
| [NumPy](https://numpy.org/citing-numpy/) | The NumPy developers | Array operations and numerical calculations. |
| [SciPy](https://scipy.org/citing-scipy/) | The SciPy developers | Signal processing, statistics, and conditional model fitting. |
| [Astropy](https://www.astropy.org/acknowledging.html) | The Astropy Collaboration and contributors | FITS input, image sections, time handling, clipped background statistics, and the optional Box Least Squares search. |
| [Numba](https://numba.pydata.org/) | The Numba developers | Compiled numerical routines used by TLS. |
| [tqdm](https://tqdm.github.io/) | Casper da Costa-Luis and the tqdm contributors | TLS's progress machinery, which the app adapts for its job progress and ETA. |

the app handles loading files, checking results, plots, exports, and the
batch/session thingies. TLS does the period search, and batman provides the
transit models used by TLS. credits for those are above.

## references for a paper

- **TLS:** Hippke, M., & Heller, R. (2019). Optimized transit detection algorithm
  to search for periodic transits of small planets. *Astronomy & Astrophysics,
  623*, A39. [Paper](https://doi.org/10.1051/0004-6361/201834672).
- **batman:** Kreidberg, L. (2015). batman: BAsic Transit Model cAlculatioN in
  Python. *Publications of the Astronomical Society of the Pacific, 127*,
  1161–1165. [Paper](https://doi.org/10.1086/683602).
- **NumPy:** Harris, C. R., et al. (2020). Array programming with NumPy.
  *Nature, 585*, 357–362. [Paper](https://doi.org/10.1038/s41586-020-2649-2).
- **SciPy:** Virtanen, P., et al. (2020). SciPy 1.0: Fundamental Algorithms for
  Scientific Computing in Python. *Nature Methods, 17*, 261–272.
  [Paper](https://doi.org/10.1038/s41592-019-0686-2).
- **Astropy:** Astropy Collaboration et al. (2013), *A&A, 558*, A33
  ([paper](https://doi.org/10.1051/0004-6361/201322068)); (2018), *AJ, 156*, 123
  ([paper](https://doi.org/10.3847/1538-3881/aabc4f)); and (2022), *ApJ, 935*, 167
  ([paper](https://doi.org/10.3847/1538-4357/ac7c74)). The project recommends
  citing all three, or the most recent when space is limited.
  [Official guidance](https://www.astropy.org/acknowledging.html).
- **Numba:** Lam, S. K., Pitrou, A., & Seibert, S. (2015). Numba: a LLVM-based
  Python JIT compiler. *Proceedings of the Second Workshop on the LLVM Compiler
  Infrastructure in HPC*. [Official citation guidance](https://numba.readthedocs.io/en/stable/user/faq.html#how-do-i-reference-cite-acknowledge-numba-in-other-work).
- **BLS, when its results contribute to the paper:** Kovács, G., Zucker, S., &
  Mazeh, T. (2002). A box-fitting algorithm in the search for periodic transits.
  *Astronomy & Astrophysics, 391*, 369–377.
  [Paper](https://doi.org/10.1051/0004-6361:20020802).

for the paper, keep the package versions and settings with the final results.
only cite the optional methods if they were actually used.

## data credits

credit the telescope/mission, archive, and whoever made the dataset once we
know where it came from. some of the old CSV sources still need checking, so
don't guess the NASA mission from the filename. keep the download link and any
required credit text with the data.

## image stuff

the image tab subtracts matching median darks, then measures the stars with
circular apertures. the sky comes from a ring around each star. aperture edges
use 8 × 8 subpixels; NumPy does the math and SciPy helps find the star centers.
timing assumptions and calibration limits get saved with the table.

method references: [Astropy image sections and scaling](https://docs.astropy.org/en/stable/io/fits/usage/image.html)
and [Photutils aperture/background/error guidance](https://photutils.readthedocs.io/en/stable/user_guide/aperture.html).

## licenses

project license: [LICENSE](LICENSE). the libraries keep their own licenses and
copyright notices. those are linked above too; paper citations don't replace them.
