# Copyright 2016, Blur Studio
#
# This file is part of Simplex.
#
# Simplex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Simplex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Simplex.  If not, see <http://www.gnu.org/licenses/>.

""" Transfer shapes between mismatched models

Given a 1:1 point correspondence, transfer the shapes from one
geometry to another. Figuring out the correspondence is currently
outside the scope of this tool, though I may release one later.

The point correspondence should look like an unordered range, and
will be used as a numpy index to get the output values. It's also
possible to invert the range if you think you've got it backwards
"""
# pylint:disable=wrong-import-position
from __future__ import absolute_import, print_function

import json

from .alembicCommon import buildSmpx, readSmpx

try:
    import numpy as np
except ImportError:
    pass


def reorderSimplexPoints(sourcePath, matchPath, outPath, invertMatch=False):
    """Transfer shape data from the sourcePath using the numpy int array
        at matchPath to make the final output at outPath

    Parameters
    ----------
    sourcePath : str
        The source .smpx file path
    matchPath : str
        The new vert order in numpy, or json format. The data should be an Nx2 array
        of integers
    outPath : str
        The new output .smpx path
    invertMatch : bool
        Whether to directly apply the match from matchPath, or whether to invert it

    Returns
    -------

    """
    jsString, counts, verts, faces, uvs, uvFaces = readSmpx(sourcePath)

    js = json.loads(jsString)
    name = js["systemName"]

    print("Loading Correspondence")
    if matchPath.endswith(".json"):
        with open(matchPath, "r") as f:
            c = json.load(f)
        c = np.array(c)
    else:
        c = np.load(matchPath)

    c = c[c[:, 0].argsort()].T[1]
    ci = c.argsort()
    if invertMatch:
        ci, c = c, ci

    print("Reordering")
    verts = verts[:, c, :]
    faces = ci[faces]

    buildSmpx(
        outPath,
        verts,
        faces,
        jsString,
        name,
        faceCounts=counts,
        uvs=uvs,
        uvFaces=uvFaces,
    )


if __name__ == "__main__":
    import os

    base = r"K:\Departments\CharacterModeling\Library\Head\MaleHead_Standard\005"
    _sourcePath = os.path.join(base, "HeadMaleStandard_High_Split_BadOrder.smpx")
    _matchPath = os.path.join(base, "Reorder.np")
    _outPath = os.path.join(base, "HeadMaleStandard_High_Split2.smpx")

    reorderSimplexPoints(_sourcePath, _matchPath, _outPath)
