"""Build a local Mac preview. Publishing and license changes are manual."""
import argparse as Argparse
from datetime import datetime as Datetime, timezone as Timezone
import hashlib as Hashlib
from importlib import metadata as Metadata
import json as Json
import os as Os
from pathlib import Path
import platform as Platform
import plistlib as Plist
import shutil as Shutil
import subprocess as Subprocess
import sys as Sys
import sysconfig as Sysconfig
import zipfile as Zipfile

from make_demo import MakeDemo

Root = Path(__file__).resolve().parents[1]
Build = Root / "build"
Dist = Root / "dist"
Version = "69"
FolderName = f"Exoplanet Transit Finder v{Version} macOS arm64"
ZipName = f"Exoplanet-Transit-Finder-v{Version}-macOS-arm64-local-preview.zip"


#MARK: keep every dependency's actual license text
def CopyNotices(Folder):
    Folder.mkdir(parents=True, exist_ok=True)
    Versions = {}
    Packages = {Item.metadata["Name"].lower(): Item for Item in Metadata.distributions()}
    # build hooks can collect a newer packaging helper from the isolated tools.
    for Item in Metadata.distributions(path=[str(Build / "packaging-tools")]):
        if Item.metadata["Name"].lower() in Packages:
            Packages[Item.metadata["Name"].lower()] = Item
    for Package in sorted(Packages.values(), key=lambda Item: Item.metadata["Name"].lower()):
        Name = Package.metadata["Name"]
        if Name.lower() in ("pip", "setuptools", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "macholib"):
            continue
        Versions[Name] = Package.version
        for File in Package.files or []:
            Relative = Path(str(File))
            if ".." in Relative.parts or Relative.is_absolute():
                continue
            if not any(Word in Relative.name.lower() for Word in ("license", "licence", "copying", "notice")):
                continue
            Source = Path(Package.locate_file(File))
            if Source.is_file():
                Output = Folder / Name / Relative
                Output.parent.mkdir(parents=True, exist_ok=True)
                Shutil.copy2(Source, Output)
    PythonLicense = Path(Sysconfig.get_path("stdlib")) / "LICENSE.txt"
    Shutil.copy2(PythonLicense, Folder / "Python-LICENSE.txt")
    (Folder / "PACKAGE_VERSIONS.json").write_text(Json.dumps(Versions, indent=2) + "\n")
    return Versions


#MARK: build commands use argument lists so paths with spaces behave
def Run(Args, Environment=None):
    print("+", " ".join(map(str, Args)), flush=True)
    Subprocess.run(list(map(str, Args)), check=True, cwd=Root, env=Environment)


def Main():
    Parser = Argparse.ArgumentParser(description=__doc__)
    Parser.add_argument("--skip-freeze", action="store_true", help="reuse build/frozen after a successful freeze")
    Args = Parser.parse_args()
    if Sys.platform != "darwin" or Platform.machine() != "arm64":
        raise SystemExit("This builder currently targets Apple Silicon Macs.")
    Build.mkdir(exist_ok=True)
    Dist.mkdir(exist_ok=True)
    Environment = dict(Os.environ)
    Environment["PYTHONPATH"] = str(Build / "packaging-tools")
    Environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for Key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS"):
        Environment[Key] = "1"
    if not Args.skip_freeze:
        Run([Sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
             "--workpath", Build / "freeze", "--distpath", Build / "frozen",
             Root / "packaging/transit_finder.spec"], Environment)
    Server = Build / "frozen/TransitFinderServer"
    if not (Server / "TransitFinderServer").is_file():
        raise SystemExit("No frozen server found. Build without --skip-freeze first.")

    #MARK: the download only gets public app files and generated examples
    Stage = Dist / FolderName
    if Stage.exists():
        Shutil.rmtree(Stage)
    Stage.mkdir()
    App = Stage / "Exoplanet Transit Finder.app"
    Contents = App / "Contents"
    Resources = Contents / "Resources"
    Executables = Contents / "MacOS"
    Executables.mkdir(parents=True)
    Resources.mkdir()
    Shutil.copytree(Server, Resources / "Server", symlinks=True)
    Run(["xcrun", "swiftc", "-target", "arm64-apple-macos14.0", "-module-cache-path",
         Build / "swift-cache", "-j2", "-O", "-framework", "AppKit",
         Root / "packaging/MacLauncher.swift", "-o", Executables / "TransitFinderLauncher"])
    Info = {"CFBundleName": "Exoplanet Transit Finder", "CFBundleDisplayName": "Exoplanet Transit Finder",
            "CFBundleIdentifier": "org.jnaor.ExoplanetTransitFinder", "CFBundleExecutable": "TransitFinderLauncher",
            "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "69.0.0",
            "CFBundleVersion": "69", "LSMinimumSystemVersion": "14.0",
            "NSPrincipalClass": "NSApplication", "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "App by Jnaor. Third-party licenses are included."}
    with (Contents / "Info.plist").open("wb") as File:
        Plist.dump(Info, File)
    MakeDemo(Resources / "Samples")
    Shutil.copytree(Resources / "Samples", Stage / "Samples")
    for Name in ("CREDITS.md", "LICENSE"):
        Shutil.copy2(Root / Name, Resources / Name)
        Shutil.copy2(Root / Name, Stage / Name)
    Shutil.copy2(Root / "packaging/QUICK_START.md", Stage / "README.md")
    Versions = CopyNotices(Resources / "ThirdPartyLicenses")
    Shutil.copytree(Resources / "ThirdPartyLicenses", Stage / "ThirdPartyLicenses")

    #MARK: ship source for exactly this build, not just an old git snapshot
    SourceFiles = [Root / "CREDITS.md", Root / "LICENSE", Root / ".gitignore"]
    for Directory in (Root / "Exoplanet data parsing tool", Root / "packaging"):
        SourceFiles += [File for File in Directory.rglob("*") if File.is_file() and "__pycache__" not in File.parts]
    Hashes = {}
    with Zipfile.ZipFile(Stage / "Source.zip", "w", Zipfile.ZIP_DEFLATED) as Archive:
        for File in sorted(SourceFiles):
            Relative = File.relative_to(Root).as_posix()
            Archive.write(File, Relative)
            Hashes[Relative] = Hashlib.sha256(File.read_bytes()).hexdigest()
    Commit = Subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Root, text=True).strip()
    Dirty = bool(Subprocess.check_output(["git", "status", "--porcelain"], cwd=Root, text=True).strip())
    BuildInfo = {"app_version": Version, "built_at": Datetime.now(Timezone.utc).isoformat(),
                 "source_commit": Commit, "source_has_uncommitted_changes": Dirty, "source_sha256": Hashes,
                 "architecture": "arm64", "minimum_binary_target": "macOS 14.0",
                 "build_machine": Platform.platform(), "python": Sys.version, "packages": Versions,
                 "signature": "ad-hoc, not Developer ID signed or notarized",
                 "public_release_approved": False,
                 "release_note": "Local preview. Resolve project CC BY-NC-ND versus bundled GPLv3 licensing before public distribution."}
    (Stage / "BUILD_INFO.json").write_text(Json.dumps(BuildInfo, indent=2) + "\n")
    Shutil.copy2(Stage / "BUILD_INFO.json", Resources / "BUILD_INFO.json")
    Run(["codesign", "--force", "--deep", "--sign", "-", App])
    Run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", App])
    Output = Dist / ZipName
    if Output.exists():
        Output.unlink()
    Run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", Stage, Output])
    Digest = Hashlib.sha256(Output.read_bytes()).hexdigest()
    (Dist / (ZipName + ".sha256")).write_text(Digest + "  " + ZipName + "\n")
    print("Local preview:", Output, flush=True)
    print("SHA256:", Digest, flush=True)


if __name__ == "__main__":
    Main()
