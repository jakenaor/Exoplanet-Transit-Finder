#!/bin/zsh

#MARK: get to the project
cd -- "${0:A:h}" || exit 1

#MARK: start the app
# use this project's python so the dependencies match.
exec .venv/bin/python "Exoplanet data parsing tool/main.py"
