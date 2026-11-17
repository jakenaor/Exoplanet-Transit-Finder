# exoplanet transit finder — mac preview

made by Jnaor · discord jake_5101 :D

this is a local preview build for apple silicon Macs. python and the science
packages are included. unzip the whole folder before opening the app.

## open it

double-click Exoplanet Transit Finder.app. the little launcher opens the app
in your default browser. keep the launcher open while you use it. use its
Quit button when done; closing a browser tab does not stop the server.

the launcher has an Open sample files button. the same examples are in Samples
next to the app. you can copy the app into your own Applications folder.

the binary target is macOS 14+. this build has only been tested on the build
machine, so older macOS versions still need a real compatibility check.
it is locally signed, not Developer ID signed or notarized.

## try a transit search

1. load Samples/synthetic_transit.csv in the transit finder tab.
2. leave View data only unchecked.
3. set the CSV time format to relative, the unit to days, and the scale to unknown.
4. use TLS, minimum period 1.4 days, maximum period 3.5 days, period oversampling 2,
   and 2 CPU workers. the smaller range keeps this demo quick.
5. analyze it. the injected period is 2.4 days.

this is synthetic data with added noise. it is not a newly discovered planet.
the known input values are in Samples/expected.json.

## try the short-data viewer

load Samples/short_observation.csv and check View data only. the dataset is
about three hours long. zoom, pan, and inspect the original flux and timestamps.

## try raw fits images

1. open FITS → light curve.
2. select all 12 files in Samples/FITS Demo/Science and all 3 in Darks.
3. upload and preview. click the left star as the target, then the right star
   as the comparison. their original-pixel centers are around (48, 50) and (136, 72).
4. use aperture 8 px, sky inner 12 px, sky outer 20 px. leave exposure-start
   selected and use up to 4 workers.
5. make the table, download it, or open it in the transit finder.

the target dims by 2% in frames 5–8. the comparison shares a changing brightness
trend, so this also checks differential photometry. these are tiny fake images.
their eleven-minute span is for the image workflow, not a period-search claim.

## files and logs

the app keeps sessions in your user Application Support folder.
image light-curve outputs go to Desktop/Current/Exoplanet Transit Finder Stuff/
Image Light Curves. source images are not overwritten.

Open log in the launcher shows startup/runtime messages. all analysis happens
on your Mac; no telescope files are uploaded to an external service.

## credits and release status

CREDITS.md contains software credits and paper citations. ThirdPartyLicenses
contains the bundled dependency notices; LICENSE is the project's current license.

this preview stays local until the CC BY-NC-ND / bundled GPLv3 licensing issue
is resolved. the license was not silently changed. source for this exact preview
is included in Source.zip, with build details in BUILD_INFO.json.
