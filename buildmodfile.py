import os
import re
import argparse
from pathlib import Path, PurePosixPath


def list_files(startpath, skips=None):
    print("ROOT: ", startpath)
    for root, dirs, files in os.walk(startpath):
        hidden = [i for i, d in enumerate(dirs) if d[0] == "."]
        if skips is not None:
            hidden += [i for i, d in enumerate(dirs) if d in skips]

        for i in sorted(hidden, reverse=True):
            dirs.pop(i)

        base = os.path.basename(root)
        level = root.replace(startpath, "").count(os.sep)
        indent = " " * 4 * (level)
        print("{}{}/".format(indent, base))
        subindent = " " * 4 * (level + 1)
        for f in files:
            if f[0] != ".":
                print("{}{}".format(subindent, f))


def main(outpath, modname, modver, modpath):
    outpath = Path(outpath).absolute()

    basepath = outpath.parent
    modpath = Path(modpath).absolute()
    modrel = modpath.relative_to(basepath)

    plugPaths = sorted(list(modpath.glob(str(Path("**") / "plug-ins"))))
    print("FOUND PLUGINS")
    print(plugPaths)

    lines = []
    for pp in plugPaths:
        rel = PurePosixPath(pp.relative_to(modpath))
        match = re.search(r"(?P<platform>win64|linux|mac)-(?P<year>\d+)", str(rel))
        if not match:
            continue
        plat, year = match["platform"], match["year"]
        lines.append(
            f"+ PLATFORM:{plat} MAYAVERSION:{year} {modname} {modver} {modrel}"
        )
        lines.append(f"plug-ins: {rel}")

        pypath = rel.replace('plug-ins', 'pyModules')
        lines.append(f"PYTHONPATH +:= {pypath}")
        lines.append("")

    if not os.path.isdir(basepath):
        os.makedirs(basepath)
    print("Writing modfile to:")
    print(outpath)
    print("With Contents:")
    print("\n".join(lines))

    with open(outpath, "w") as f:
        f.write("\n".join(lines))


def parse():
    parser = argparse.ArgumentParser(
        prog="buildmodfile",
        description="builds a mod file ensuring that plugins are loaded for the proper maya versions",
    )
    parser.add_argument("outpath", help="The output filepath")
    parser.add_argument("-n", "--name", help="The name of the module", required=True)
    parser.add_argument("-v", "--version", help="The version of the module", default="1.0.0")
    parser.add_argument("-p", "--path", help="The path to the module folder", required=True)
    args = parser.parse_args()

    list_files(os.getcwd(), skips=['eigen', 'rapidjson', 'os'])
    main(args.outpath, args.name, args.version, args.path)


if __name__ == "__main__":
    parse()
