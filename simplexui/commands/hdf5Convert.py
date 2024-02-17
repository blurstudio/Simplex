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

from __future__ import absolute_import

import json

from .alembicCommon import buildSmpx, readSmpx


def hdf5Convert(inPath, outPath, ogawa=False):
    """Load and parse all the data from a simplex file

    Parameters
    ----------
    inPath : str
        The input .smpx file path
    outPath : str
        The output .smpx file path
    ogawa : bool
        Whether to write out in Ogawa format. Defaults False

    Returns
    -------

    """
    jsString, counts, verts, faces, uvs, uvFaces = readSmpx(inPath)

    js = json.loads(jsString)
    name = js["systemName"]

    buildSmpx(
        outPath,
        verts,
        faces,
        jsString,
        name,
        faceCounts=counts,
        uvs=uvs,
        uvFaces=uvFaces,
        ogawa=ogawa,
    )


if __name__ == "__main__":
    inPath = r"D:\Users\tyler\Desktop\Head_Morphs_Main_Head-Face_v0010.smpx"
    outPath = r"D:\Users\tyler\Desktop\Head_ogawa.smpx"
    hdf5Convert(inPath, outPath, ogawa=True)
