import logging
import importlib.util
import os
import sys
import zipfile
from pathlib import Path

from maya import cmds, mel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


sys.dont_write_bytecode = True


def install_numpy(pyexe, target):
    """Install numpy to a particular folder

    Arguments:
        pyexe (str|Path): A path to the current python executable
        target (str|Path): The folder to install to

    Raises:
        CalledProcessError: If the pip command fails
    """
    import subprocess

    cmd = [str(pyexe), "-m", "pip", "install", "--target", str(target), "numpy"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if proc.returncode != 0:
        logging.critical("\n\n")
        logging.critical(proc.stdout)
        logging.critical("\n\n")
        cmds.confirmDialog(
            title="Simplex Install Error",
            message="Numpy install failed",
            button=["OK"],
        )
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)


def install_qtpy(pyexe, target):
    """Install Qt.py to a particular folder

    Arguments:
        pyexe (str|Path): A path to the current python executable
        target (str|Path): The folder to install to

    Raises:
        CalledProcessError: If the pip command fails
    """
    import subprocess

    cmd = [str(pyexe), "-m", "pip", "install", "--target", str(target), "Qt.py"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if proc.returncode != 0:
        logging.critical("\n\n")
        logging.critical(proc.stdout)
        logging.critical("\n\n")
        cmds.confirmDialog(
            title="Qt.py Install Error",
            message="Qt.py install failed",
            button=["OK"],
        )
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)


def get_latest_git_release(user, repo, asset_regex, out_path):
    """Get the latest github release from a particular user/repo and download
    it to a specified path

    Arguments:
        user (str): The github user name to download from
        repo (str): The github repo name to download
        asset_regex (str): A regex to match against the name of the asset
        out_path (str|Path): A filepath where the release should be downloaded to

    Returns:
        Path: The path that the file was downloaded to. This *technically* may be
            different from the provided out_path

    Raises:
        ValueError: If the latest repo asset can't be found for download
    """
    import json
    import re
    import urllib.request

    latest_link = f"https://api.github.com/repos/{user}/{repo}/releases/latest"
    f = urllib.request.urlopen(latest_link)
    latest_release_data = json.loads(f.read())
    assets = latest_release_data.get("assets", [])
    download_url = None
    for a in assets:
        if re.match(asset_regex, a["name"]):
            download_url = a["browser_download_url"]
            break

    if download_url is None:
        asset_names = "\n".join([a["name"] for a in assets])
        msg = f"regex: {asset_regex}\nnames:\n{asset_names}"
        cmds.confirmDialog(
            title="Simplex Install Error",
            message="Release Download Failed",
            button=["OK"],
        )

        raise ValueError(
            f"Cannot find latest {user}/{repo} version to download.\nCheck your asset_regex\n{msg}"
        )

    out_path = Path(out_path)
    outFolder = out_path.parent
    outFolder.mkdir(exist_ok=True)
    logger.info("Downloading latest simplex")
    logger.info(f"from: {download_url}")
    logger.info(f"to: {out_path}")
    path, _headers = urllib.request.urlretrieve(download_url, filename=out_path)
    return Path(path)


def get_mayapy_path():
    """Get the path to the mayapy executable"""
    binFolder = Path(sys.executable).parent
    if sys.platform == "win32":
        return binFolder / "mayapy.exe"
    elif sys.platform == "darwin":
        return binFolder / "mayapy"
    elif sys.platform == "linux":
        return binFolder / "mayapy"
    cmds.confirmDialog(
        title="Simplex Install Error",
        message=f"Unsupported Platform: {sys.platform}",
        button=["OK"],
    )

    raise RuntimeError(f"Current platform is unsupported: {sys.platform}")


def get_numpy_simplex_target(mod_folder):
    """Get the target path for the numpy simplex install"""

    if sys.platform == "win32":
        platform = "win64"
    elif sys.platform == "darwin":
        platform = "mac"
    elif sys.platform == "linux":
        platform = "linux"
    else:
        cmds.confirmDialog(
            title="Simplex Install Error",
            message=f"Unsupported Platform: {sys.platform}",
            button=["OK"],
        )
        raise RuntimeError(f"Current platform is unsupported: {sys.platform}")

    year = cmds.about(majorVersion=True)
    nppath = mod_folder / "simplex" / f"{platform}-{year}" / "pyModules"
    return nppath


def onMayaDroppedPythonFile(_obj):
    """This function will get run when you drag/drop this python script onto maya"""
    try:
        # Ensure that people will report a full error
        cmds.optionVar(intValue=("stackTraceIsOn", 1))
        mel.eval('synchronizeScriptEditorOption(1, "StackTraceMenuItem")')

        mod_folder = Path(cmds.internalVar(userAppDir=True)) / "modules"
        modfile = mod_folder / "simplex.mod"
        simplex_zip = mod_folder / "simplex.zip"
        moddir = mod_folder / "simplex"
        if modfile.is_file() != moddir.is_dir():
            msg = f"Simplex module is partially installed.\nPlease delete {modfile} and {moddir} and try again"
            cmds.confirmDialog(
                title="Simplex Install Error",
                message=msg,
                button=["OK"],
            )
            raise ValueError(msg)

        if simplex_zip.is_file():
            os.remove(simplex_zip)

        # This will overwrite the existing install, but will leave any numpy installs alone
        simplex_zip = get_latest_git_release(
            "blurstudio",
            "simplex",
            r"simplex-v\d+\.\d+\.\d+\.zip",
            simplex_zip,
        )

        if not simplex_zip.is_file():
            cmds.confirmDialog(
                title="Simplex Install Error",
                message="Zip file download failed",
                button=["OK"],
            )
            raise RuntimeError("Download of simplex zip failed")

        with zipfile.ZipFile(simplex_zip, "r") as zip_ref:
            members = [m for m in zip_ref.namelist() if m.startswith("modules/")]
            zip_ref.extractall(mod_folder.parent, members=members)

        os.remove(simplex_zip)

        mayapy = get_mayapy_path()
        target = get_numpy_simplex_target(mod_folder)

        if importlib.util.find_spec("numpy") is None:
            install_numpy(mayapy, target)
        else:
            logger.info("Numpy is already installed for this version of maya")

        if importlib.util.find_spec("Qt") is None:
            install_qtpy(mayapy, target)
        else:
            logger.info("Qt.py is already installed for this version of maya")

    finally:
        sys.dont_write_bytecode = False

    cmds.confirmDialog(
        title="Simplex Installed",
        message="Simplex installation complete",
        button=["OK"],
    )
