# credits

Exoplanet Transit Finder is a project by **Jnaor**.
Contact: **jake_5101** on Discord :D

## software behind the app

| Software | Credit | Used for |
| --- | --- | --- |
| [Transit Least Squares](https://github.com/hippke/tls) | Michael Hippke, René Heller, and contributors | The reference transit-search engine. The app currently uses TLS 1.32. |
| [batman](https://lkreidberg.github.io/batman/docs/html/index.html) | Laura Kreidberg and contributors | Physical transit templates inside TLS 1.32; also used for the app's injection tests. |
| [NumPy](https://numpy.org/citing-numpy/) | The NumPy developers | Array operations and numerical calculations. |
| [SciPy](https://scipy.org/citing-scipy/) | The SciPy developers | Signal processing, statistics, and conditional model fitting. |
| [Astropy](https://www.astropy.org/acknowledging.html) | The Astropy Collaboration and contributors | FITS input and the optional Box Least Squares search. |
| [Numba](https://numba.pydata.org/) | The Numba developers | Compiled numerical routines used by TLS. |
| [tqdm](https://tqdm.github.io/) | Casper da Costa-Luis and the tqdm contributors | TLS's progress machinery, which the app adapts for its job progress and ETA. |

The app adds preprocessing, event checks, candidate scoring, plots, exports,
and batch/session handling around these tools. The original TLS search and
batman transit models are credited to their authors above.

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

Record the versions and settings from the final analysis results alongside the
paper. Acknowledging a package here does not establish that every optional
method was used in a particular run.

## data credits

Credit each dataset's actual telescope/mission, archive, instrument, and
reduction pipeline when its source is confirmed. The original sources of the
current test CSVs remain unverified, so no particular NASA mission or archive
is assigned credit based only on a filename. Keep the original download link,
data-product identifier, and required acknowledgment wording with each dataset.

## licenses

The project's license is in [LICENSE](LICENSE). Third-party software retains its
own licenses and copyright notices. The links above lead to the original
projects and their notices; these research references do not replace them.
