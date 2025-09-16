import os
import subprocess
import sys

VERSION_FILE = "version.txt"


def main(srcroot, gitpath):
    """
    When building a python wheel, the build system copies the entire source tree into a new folder
    but it doesn't seem to include git tags, or it doesn't check out the git tags, or *something*
    So I'm writing out a version.txt file that this function will read and pass along to the
    meson project() function call
    """
    # If version.txt already exists, use it
    src_file = os.path.join(srcroot, VERSION_FILE)
    if os.path.exists(src_file):
        with open(src_file) as f:
            v = f.read().strip()
    else:
        # Otherwise, try git describe
        try:
            # fmt: off
            v = subprocess.check_output(
                [gitpath, "describe", "--tags", "--always", "--match", "v[0-9]*", "--abbrev=0"],
                text=True,
            ).strip()
            # fmt: on
        except Exception:
            v = "0.0.1"  # fallback if not in a git repo

    print(v)


if __name__ == "__main__":
    srcroot = sys.argv[1]
    gitpath = sys.argv[2]
    sys.exit(main(srcroot, gitpath))
