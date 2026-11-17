#MARK: freeze the server, the little mac window gets built separately
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

Root = Path(SPECPATH).parent
AppDir = Root / "Exoplanet data parsing tool"
DataThings = [(str(AppDir / "static"), "static")]
DataThings += collect_data_files("transitleastsquares")
for Package in ("numpy", "scipy", "astropy", "transitleastsquares", "batman-package", "numba", "llvmlite", "tqdm", "astropy-iers-data", "pyerfa", "packaging"):
    DataThings += copy_metadata(Package)

AnalysisThing = Analysis(
    [str(Root / "packaging/frozen_entry.py")],
    pathex=[str(AppDir)],
    binaries=[],
    datas=DataThings,
    hiddenimports=["transitleastsquares.main", "transitleastsquares.stats", "astropy.timeseries", "scipy.optimize", "llvmlite.binding"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "setuptools"],
    # tls progress/source inspection and numba both need real module files.
    module_collection_mode={"transitleastsquares": "pyz+py"},
)
PythonBits = PYZ(AnalysisThing.pure)
ServerThing = EXE(
    PythonBits, AnalysisThing.scripts, [],
    exclude_binaries=True, name="TransitFinderServer", console=True,
    debug=False, strip=False, upx=False, target_arch="arm64", codesign_identity=None,
)
ServerFolder = COLLECT(
    ServerThing, AnalysisThing.binaries, AnalysisThing.datas,
    strip=False, upx=False, name="TransitFinderServer",
)
