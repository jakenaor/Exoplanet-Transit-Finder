# exoplanet transit finder

a python thingy for looking through telescope data and finding possible
exoplanet transits. im building it for my exoplanet research project, but
if u have your own light curves, u can try it too :D

it opens in your browser. all the actual processing happens on your computer

## what it does

- search light curves using Transit Least Squares, or BLS if u want
- process multiple datasets in a batch
- look at finished files while the rest of the batch is still running
- inspect results with interactive graphs, phase-folded views, and transit stacks
- view short datasets without trying to force a period search
- cut big gaps out of the observation view (the original timestamps stay intact for analysis and exports)
- save sessions and export results
- turn raw FITS images + matching darks into time/flux tables in a second tab

TLS does the period search. this app handles the file/plot/batch thingies around
it. the people who made the libraries deserve credit, so those + the paper
references are in [CREDITS.md](CREDITS.md)

## how to run it from the code

u need **Python 3.9–3.12**. the current test enviroment uses 3.9.6.
Python 3.13+ removed [cgi](https://docs.python.org/3/library/cgi.html),
which this thing still uses.

these commands are for a macOS/Linux terminal:

~~~sh
git clone https://github.com/jakenaor/Exoplanet-Transit-Finder.git
cd Exoplanet-Transit-Finder
python3.12 -m venv .venv
.venv/bin/python -m pip install -r "Exoplanet data parsing tool/requirements.txt"
.venv/bin/python "Exoplanet data parsing tool/main.py"
~~~

if u already have a working .venv in this repo, just run the last line.
keep the damn quotes around the paths. the folder name has spaces lol

it should open your browser. if it doesnt, copy the localhost URL from the
terminal into your browser. it tries ports 8000–8010 until it finds a free one.

keep the terminal running. **Ctrl+C** stops the server. closing a browser tab doesnt stop the program

## actually using it

upload a CSV with Time and Flux columns, or a FITS light-curve table.
set the time format/unit/scale to match the data. if u just want to look at a
short dataset, check **View data only**.

for raw camera images, go to **FITS → light curve**. choose the science images
and matching darks, then upload and preview. click the target star, then any
comparison stars u want to use. check the aperture and sky rings before making
the table. this tab can use up to 4 workers.

the Mac preview includes synthetic CSVs + a tiny FITS dataset to try everything.
[the quick-start guide](packaging/QUICK_START.md) has the settings and known
input values for those examples. theyre fake data, not real discoveries.

## the mac download

for apple silicon mac ONLY. no windows. fuck you, windows.
(im kidding ill release for windows later lol) (please dont sue me)

the build targets macOS 14+, but its only been tested on macOS 26.6.2 so far.
python + the required libraries are already included

unzip the whole folder and open Exoplanet Transit Finder.app. it opens in your
browser; keep the launcher running, then use **Quit** when youre done.
the launcher also has buttons for the sample files and logs.

its locally signed, but not Apple-notarized.
[build instructions + release status](packaging/README.md) are in packaging/.

## stuff that still needs work

still alpha. a dip isnt automatically "holy shit i found a planet"
candidate signals need further checking before calling them planets.

FITS calibration currently uses darks only. no flats yet.
star tracking is local, so split meridian flips, rotations, and different
fields into seperate runs. timing assumptions + measurement flags are saved
in the metadata. no barycentric correction is applied.

## credits + license

made by **Jnaor**

discord: **jake_5101**, nick **Hydroxyl** :D

project license is in [LICENSE](LICENSE). the libraries keep their own licenses.
authors + references are in [CREDITS.md](CREDITS.md).
