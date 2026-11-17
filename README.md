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

## trying the datasets in this repo

the [datasets/](datasets/) folder has seven CSVs ready to load. they already
have Time and Flux columns, so use the **Transit finder** tab for these

if u cloned the repo, theyre already in that folder. if u only downloaded the
Mac app, download a ZIP of this repo too and grab the datasets/ folder from it.
the app's bundled Samples folder has seperate synthetic examples

| file | data points |
| --- | ---: |
| [hd209458_time_flux.csv](datasets/hd209458_time_flux.csv) | 6,878 |
| [wasp4_time_flux.csv](datasets/wasp4_time_flux.csv) | 47,763 |
| [wasp18_time_flux.csv](datasets/wasp18_time_flux.csv) | 31,761 |
| [wasp19_time_flux.csv](datasets/wasp19_time_flux.csv) | 30,816 |
| [wasp43_time_flux.csv](datasets/wasp43_time_flux.csv) | 28,558 |
| [trappist1_time_flux.csv](datasets/trappist1_time_flux.csv) | 80,108 |
| [no_exoplanet_just_pure_noiselightcurve.csv](datasets/no_exoplanet_just_pure_noiselightcurve.csv) | 5,600 |

### just look at a light curve first

1. open the app and stay on **Transit finder**
2. click **Drop CSV or FITS files here**, or drag a CSV onto it.
   start with hd209458_time_flux.csv before throwing the whole batch at it lol
3. under **Detection → CSV time metadata**, set **Time format** and **Time scale**
   to **Unknown**. leave **Input time unit** on **Days** for this test workflow
4. leave **Exposure per sample (seconds)** blank. these files dont include exposure durations
5. check **View data only (skip period search)**, then click **Analyze files**
6. inspect the graph in **Observation viewer**. zoom, pan, and hover over points

the Days setting is an assumption used for these test files. their headers dont
confirm the original time unit, JD/BJD convention, UTC/TDB scale, or mission.
keep the clock format/scale Unknown until the original source docs are available;
a big-looking Time value by itself doesnt establish any of that

some files have huge gaps. **Cut large gaps in Observation viewer** shortens
those gaps on the graph; the original timestamps stay intact for searches and
exports. set the minimum gap before processing if u want to use it

### actually search for transits

uncheck **View data only**, choose **Physical TLS** under **Search mode**, then
click **Analyze files** again. start with one file and use up to 4 CPU workers
if u dont want the whole batch competing with everything else on your computer

**Min period days** and **Max period days** can stay blank for a general search.
if u set them for a focused test, clear them before switching to another target.
TLS can take a while, especially with a large file or a wide search range

to run a batch, select multiple CSVs together before clicking **Analyze files**.
use **Batch Results → Processed file** to switch between finished results while
the remaining files keep running. wait for the batch to finish or cancel it
before replacing the uploaded files

the file labelled no_exoplanet_just_pure_noiselightcurve is the noise-labelled
control. trappist1 is the larger, messier one to inspect and experiment with.
the filenames are labels, not proof of what a particular fitted dip represents

## your own data + raw images

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
