# mac build thingy

this makes an apple silicon mac app with its own python and science packages.
the launcher opens the browser and has buttons for the sample folder and quitting.

## build

from the repo root, with the normal app dependencies already in .venv:

    .venv/bin/python -m pip install --target build/packaging-tools -r packaging/requirements-build.txt
    .venv/bin/python packaging/build_macos.py

the finished zip goes in dist/. xcode command line tools are needed to compile
the little AppKit launcher. the app itself does not need xcode or python.

the build is arm64, with macOS 14 as its minimum binary target. it still needs
testing on older supported macOS versions; only the current build machine has
been checked. the app is signed locally, without an Apple Developer ID or
notarization. do not describe that as a notarized release.

## before publishing

the repo currently uses CC BY-NC-ND 4.0. batman, which TLS imports, is GPLv3.
those terms need a licensing decision before a combined public binary release.
the builder keeps the current license and includes third-party notices. it does
not publish anything or change the project's license.

the examples are generated synthetic data. no private telescope frames,
saved sessions, API keys, or .venv folder belong in the download.
