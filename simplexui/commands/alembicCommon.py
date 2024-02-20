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

""" Alembic files can be difficult to work with, and can be *very* slow in Python
This is a library of convenience functions with the numpy speed optimizations
"""
from __future__ import absolute_import, print_function

import os

import six
from alembic.Abc import IArchive, OArchive, OStringProperty
from alembic.AbcGeom import (
    GeometryScope,
    IPolyMesh,
    IXform,
    ON3fGeomParamSample,
    OPolyMesh,
    OPolyMeshSchemaSample,
    OV2fGeomParamSample,
    OXform,
)
from imath import IntArray, UnsignedIntArray, V2f, V2fArray, V3fArray
from six.moves import range, zip

try:
    import numpy as np
except ImportError:
    np = None
    arrayToNumpy = None
else:
    try:
        from imathnumpy import arrayToNumpy  # pylint:disable=no-name-in-module
    except ImportError:
        arrayToNumpy = None


def pbPrint(pBar, message=None, val=None, maxVal=None, _pbPrintLastComma=[]):
    """A function that handles displaying messages in a QProgressDialog or printing to stdout

    Don't forget to call QApplication.processEvents() after using this function

    Parameters
    ----------
    pBar : QProgressDialog or None
        An optional progress bar
    message : str or None
        An optional message to display
    val : int or None
        An optional progress value to display
    maxVal : int or None
        An optional maximum value to display
    _pbPrintLastComma: object
        INTERNAL USE ONLY
    """
    if pBar is not None:
        if val is not None:
            pBar.setValue(val)
        if message is not None:
            pBar.setLabelText(message)
    else:
        if message is not None:
            if val is not None:
                if maxVal is not None:
                    print(
                        message, "{0: <4} of {1: <4}\r".format(val + 1, maxVal), end=" "
                    )
                else:
                    print(message, "{0: <4}\r".format(val + 1), end=" ")
                # This is the ugliest, most terrible thing I think I've ever written
                # Abusing the static default object to check if the last time
                # this function was used, there was a trailing comma
                # But damn if it doesn't make me laugh
                if not _pbPrintLastComma:
                    _pbPrintLastComma.append("")
            else:
                if _pbPrintLastComma:
                    print(_pbPrintLastComma.pop())
                print(message)


def mkArray(aType, iList):
    """Makes the alembic-usable c++ typed 2-d arrays

    Parameters
    ----------
    aType : imath type
        The type of the output array
    iList : list or np.array
        The input iterable.

    Returns
    -------
    : aType
        The input list translated into an aType array
    """
    if isinstance(iList, aType):
        return iList

    if np is None:
        array = aType(len(iList))
        for i in range(len(iList)):
            array[i] = tuple(iList[i])
        return array
    elif arrayToNumpy is None:
        array = aType(len(iList))
        for i in range(len(iList)):
            array[i] = tuple(iList[i].tolist())
        return array
    else:
        iList = np.array(iList)
        array = aType(len(iList))
        memView = arrayToNumpy(array)
        np.copyto(memView, iList)
        return array


def mk1dArray(aType, iList):
    """Makes the alembic-usable c++ typed 1-d arrays

    Parameters
    ----------
    aType : imath type
        The type of the output array
    iList : list or np.array
        The input iterable.

    Returns
    -------
    : aType
        The input list translated into an aType array
    """
    if isinstance(iList, aType):
        return iList
    if np is None or arrayToNumpy is None or aType is UnsignedIntArray:
        array = aType(len(iList))
        for i in range(len(iList)):
            # Gotta cast to int because an "int" from numpy has
            # the type np.int32, which makes this conversion angry
            array[i] = int(iList[i])
        return array
    else:
        iList = np.array(iList)
        array = aType(len(iList))
        memView = arrayToNumpy(array)
        np.copyto(memView, iList)
        return array


def mkSampleVertexPoints(pts):
    """Make an imath array of vertices

    Parameters
    ----------
    pts : list or np.array
        The input points

    Returns
    -------
    : V3fArray
        The output list
    """
    return mkArray(V3fArray, pts)


def mkSampleIntArray(vals):
    """Make an imath array of integers

    Parameters
    ----------
    pts : list or np.array
        The input integers

    Returns
    -------
    : IntArray
        The output list
    """
    return mk1dArray(IntArray, vals)


def mkSampleUIntArray(vals):
    """Make an imath array of unsigned integers

    Parameters
    ----------
    pts : list or np.array
        The input unsigned integers

    Returns
    -------
    : UnsignedIntArray
        The output list
    """
    return mk1dArray(UnsignedIntArray, vals)


def mkSampleUvArray(uvs):
    """Make an imath array of uvs

    Parameters
    ----------
    uvs : list or np.array
        The input uvs

    Returns
    -------
    : V2fArray
        The output list
    """
    array = V2fArray(len(uvs))
    setter = V2f(0, 0)
    for i in range(len(uvs)):
        setter.setValue(float(uvs[i][0]), float(uvs[i][1]))
        array[i] = setter
    return array


def mkUvSample(uvs, indexes=None):
    """Take an array, and make a poly mesh sample of the uvs

    Parameters
    ----------
    uvs : list or np.array
        The input uvs
    indexes : list or np.array or None
        The optional face indices of the uvs

    Returns
    -------
    : OV2fGeomParamSample
        The UV sample
    """
    ary = mkSampleUvArray(uvs)
    if indexes is None:
        return OV2fGeomParamSample(ary, GeometryScope.kFacevaryingScope)
    idxs = mkSampleUIntArray(indexes)
    return OV2fGeomParamSample(ary, idxs, GeometryScope.kFacevaryingScope)


def mkNormalSample(norms, indexes=None):
    """Take an array, and make a poly mesh sample of the normals

    Parameters
    ----------
    norms : list or np.array
        The input normals
    indexes : list or np.array or None
        The optional face indices of the normals

    Returns
    -------
    : ON3fGeomParamSample
        The Normal sample
    """
    ary = mkArray(V3fArray, norms)
    if indexes is None:
        return ON3fGeomParamSample(ary, GeometryScope.kFacevaryingScope)
    idxs = mkSampleUIntArray(indexes)
    return ON3fGeomParamSample(ary, idxs, GeometryScope.kFacevaryingScope)


def setAlembicSample(
    omeshSch, points, faceCount, faceIndex, bounds=None, uvs=None, normals=None
):
    """Set an alembic sample to the output mesh with the given properties"""
    # Do it this way because the defaults for these arguments are some value other than None
    kwargs = {}
    if uvs is not None:
        kwargs["iUVs"] = uvs
    if normals is not None:
        kwargs["iNormals"] = normals

    s = OPolyMeshSchemaSample(points, faceIndex, faceCount, **kwargs)
    if bounds is not None:
        omeshSch.getChildBoundsProperty().setValue(bounds)
    omeshSch.set(s)


def getSampleArray(imesh, pBar=None):
    """Get the per-frame vertex positions for a mesh

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : np.array or list
        The per-frame vertex positions
    """
    meshSchema = imesh.getSchema()
    posProp = meshSchema.getPositionsProperty()
    numShapes = len(posProp.samples)
    if arrayToNumpy is not None:
        shapes = np.empty((len(posProp.samples), len(posProp.samples[0]), 3))
        for i, s in enumerate(posProp.samples):
            pbPrint(pBar, message="Reading Shape", val=i, maxVal=numShapes)
            shapes[i] = arrayToNumpy(s)
    elif np is not None:
        shapes = []
        for i, s in enumerate(posProp.samples):
            pbPrint(pBar, message="Reading Shape", val=i, maxVal=numShapes)
            shapes.append((list(s.x), list(s.y), list(s.z)))
        shapes = np.array(shapes)
        shapes = shapes.transpose((0, 2, 1))
    else:
        shapes = []
        for i, s in enumerate(posProp.samples):
            pbPrint(pBar, message="Reading Shape", val=i, maxVal=numShapes)
            shapes.append(s)
    pbPrint(pBar, message="Done Reading")
    return shapes


def getStaticMeshData(imesh):
    """Get all the generally non-changing data for a mesh

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : IntArray
        A flat alembic array of vertex indices for the faces
    : IntArray
        The number of vertices per face
    """
    sch = imesh.getSchema()
    faces = sch.getFaceIndicesProperty().samples[0]
    counts = sch.getFaceCountsProperty().samples[0]
    return faces, counts


def getStaticMeshArrays(imesh):
    """Get all the generally non-changing data for a mesh as numpy arrays

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : np.array or list
        A flat of vertex indices for the faces as np.array if possible
    : np.array or list
        The number of vertices per face as np.array if possible
    """
    faces, counts = getStaticMeshData(imesh)
    if arrayToNumpy is not None:
        faces = arrayToNumpy(faces).copy()
        counts = arrayToNumpy(counts).copy()
    elif np is not None:
        faces, counts = np.array(faces), np.array(counts)
    else:
        faces, counts = list(faces), list(counts)
    return faces, counts


def getUvSample(imesh):
    """Get the UV's for a mesh

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : OV2fGeomParamSample
        The UV Sample
    """
    imeshsch = imesh.getSchema()
    uvParam = imeshsch.getUVsParam()

    if not uvParam.valid():
        return None

    uvValue = uvParam.getValueProperty().getValue()
    if uvParam.isIndexed():
        idxValue = uvParam.getIndexProperty().getValue()
        uv = OV2fGeomParamSample(uvValue, idxValue, GeometryScope.kFacevaryingScope)
    else:
        uv = OV2fGeomParamSample(uvValue, GeometryScope.kFacevaryingScope)
    return uv


def getUvArray(imesh):
    """Get the uv positions for a mesh

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : list or np.array or None
        The UVs if they exist as a numpy array if possible
    """
    imeshsch = imesh.getSchema()
    uvParam = imeshsch.getUVsParam()
    if uvParam.valid():
        uvProp = uvParam.getValueProperty()
        uvVals = uvProp.getValue()
        # imathNumpy doesn't work on V2f arrays
        # so I have to use one of the slow ways
        uv = list(zip(uvVals.x, uvVals.y))
        if np is not None:
            uv = np.array(uv)
    else:
        uv = None
    return uv


def getFlatUvFaces(imesh):
    """Get the UV structure for a mesh if it's indexed. If un-indexed, return None
        This means that if we have valid UVs, but invalid uvFaces, then we're un-indexed
        and can handle the data appropriately for export without keeping track of index-ness

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : [int, ...] or np.array
        The UVFace structure
    : bool
        Whether we share uvs between uvFaces (True), or we have a uv per face-vertex (False)
    """
    sch = imesh.getSchema()
    iuvs = sch.getUVsParam()
    idxs = None
    indexed = None
    if iuvs.valid():
        if iuvs.isIndexed():
            indexed = True
            idxs = iuvs.getIndexProperty().getValue()
            # if arrayToNumpy is not None:
            # idxs = arrayToNumpy(idxs).copy()
            # elif np is not None:
            if np is not None:
                idxs = np.array(idxs)
            else:
                idxs = list(idxs)
        else:
            indexed = False
            rawCount = sum(list(sch.getFaceCountsProperty().samples[0]))
            if np is not None:
                idxs = np.arange(rawCount)
            else:
                idxs = list(range(rawCount))

    return idxs, indexed


def getUvFaces(imesh):
    """Get the UV structure for a mesh if it's indexed. If un-indexed, return None
        This means that if we have valid UVs, but invalid uvFaces, then we're un-indexed
        and can handle the data appropriately for export without keeping track of index-ness

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : [[int, ...], ...]
        The UVFace structure
    """
    sch = imesh.getSchema()
    rawCounts = sch.getFaceCountsProperty().samples[0]
    iuvs = sch.getUVsParam()
    uvFaces = None
    if iuvs.valid():
        uvFaces = []
        uvCounter = 0
        if iuvs.isIndexed():
            idxs = list(iuvs.getIndexProperty().getValue())
            for count in rawCounts:
                uvFaces.append(list(idxs[uvCounter : uvCounter + count]))
                uvCounter += count
    return uvFaces


def getMeshFaces(imesh):
    """Get The vertex indices used per face

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : [[int, ...], ...]
        The UVFace structure
    """
    rawFaces, rawCounts = getStaticMeshData(imesh)
    faces = []
    ptr = 0
    for count in rawCounts:
        faces.append(list(rawFaces[ptr : ptr + count]))
        ptr += count
    return faces


def getPointCount(imesh):
    """Get the number of vertices in a mesh

    Parameters
    ----------
    imesh : IPolyMesh
        The input alembic mesh object

    Returns
    -------
    : int
        The number of vertices in the mesh
    """
    meshSchema = imesh.getSchema()
    posProp = meshSchema.getPositionsProperty()
    return len(posProp.samples[0])


def findAlembicObject(obj, abcType=None, name=None):
    """
    Finds a single object in an alembic archive by name and/or type
    If only type is specified, then the first object of that type
    encountered will be returned
    """
    md = obj.getMetaData()
    if abcType is None:
        if name is None or obj.getName() == name:
            return obj
    elif abcType.matches(md):
        if name is None or obj.getName() == name:
            return abcType(obj.getParent(), obj.getName())
    for child in obj.children:
        out = findAlembicObject(child, abcType, name)
        if out is not None:
            return out
    return None


def findAllAlembicObjects(obj, abcType=None, out=None):
    """Finds all objects of a type in an alembic archive"""
    md = obj.getMetaData()
    out = [] if out is None else out
    if abcType is None:
        out.append(obj)
    elif abcType.matches(md):
        out.append(abcType(obj.getParent(), obj.getName()))
    for child in obj.children:
        findAllAlembicObjects(child, abcType, out)
    return out


def getTypedIObject(obj):
    from alembic.AbcGeom import (
        ICamera,
        ICurves,
        ILight,
        INuPatch,
        IPoints,
        IPolyMesh,
        ISubD,
        IXform,
    )

    md = obj.getMetaData()
    for abcType in (
        IXform,
        IPolyMesh,
        ICamera,
        ICurves,
        ILight,
        INuPatch,
        IPoints,
        ISubD,
    ):
        if abcType.matches(md):
            return abcType(obj.getParent(), obj.getName())
    return None


def getMesh(infile):
    """Get the first found mesh object from the alembic filepath"""
    iarch = IArchive(infile)
    ipolymsh = findAlembicObject(iarch.getTop(), abcType=IPolyMesh)
    return ipolymsh


def writeStringProperty(props, key, value, ogawa=True):
    """Write the definition string to an alembic OObject

    HDF5 (which we must still support) has a character limit
    to string properties. Splitting the string must be handled
    in a uniform way, so this function must be used

    Parameters
    ----------
    props : OCompoundProperty
        The alembic OObject properties
    value : str
        The simplex definition string
    ogawa : bool
        If the output is ogawa

    """
    if len(value) > 65000 and not ogawa:
        value = str(value)
        numChunks = (len(value) // 65000) + 1
        chunkSize = (len(value) // numChunks) + 1
        for c in range(numChunks):
            prop = OStringProperty(props, "{0}{1}".format(key, c))
            prop.setValue(value[chunkSize * c : chunkSize * (c + 1)])
    else:
        prop = OStringProperty(props, str(key))
        prop.setValue(str(value))


def readStringProperty(props, key):
    """Read the definition string from an alembic OObject

    HDF5 (which we must still support) has a character limit
    to string properties. Splitting the string must be handled
    in a uniform way, so this function must be used

    Parameters
    ----------
    props : ICompoundProperty
        The alembic IObject properties

    Returns
    -------
    : str
        The simplex definition string
    """
    if not props.valid():
        raise ValueError(".smpx file is missing the alembic user properties")

    try:
        prop = props.getProperty(key)
    except KeyError:
        parts = []
        for c in range(10):
            try:
                prop = props.getProperty("{0}{1}".format(key, c))
            except KeyError:
                if c == 0:
                    raise
                break
            else:
                parts.append(prop.getValue())
        else:
            raise ValueError("That is a HELL of a long simplex definition")
        jsString = "".join(parts)
    else:
        jsString = prop.getValue()

    return jsString


def flattenFaces(faces):
    """Take a nested list representation of faces
    and turn it into a flat face/count representation

    Parameters
    ----------
    faces : [[int, ...], ...]
        The nested list representation

    Returns
    -------
    : np.array or list
        The flat list of face connectivity
    : np.array or list
        The flat list of vertices per face

    """
    faceCounts, faceIdxs = [], []
    for f in faces:
        faceCounts.append(len(f))
        faceIdxs.extend(f)
    if np is not None:
        return np.array(faceCounts), np.array(faceIdxs)
    return faceCounts, faceIdxs


def unflattenFaces(faces, counts):
    """Take a flat face/count representation of faces
    and turn it into a nested list representation

    Parameters
    ----------
    faces : np.array
        The flat list of face connectivity
    counts : np.array
        The flat list of vertices per face

    Returns
    -------
    : [[int, ...], ...]
        The nested list representation
    """
    out, ptr = [], 0
    for c in counts:
        out.append(faces[ptr : ptr + c].tolist())
        ptr += c
    return out


def buildAbc(
    outPath,
    points,
    faces,
    faceCounts=None,
    uvs=None,
    uvFaces=None,
    normals=None,
    normFaces=None,
    name="polymsh",
    shapeSuffix="Shape",
    transformSuffix="",
    propDict=None,
    ogawa=True,
    pBar=None,
):
    """
    Build a single-mesh alembic file from all of the non-alembic raw data

    Parameters
    ----------
    outPath: str
        The output path for the alembic file
    points: list or ndarray
        The list or array of points. Single multiple frames supported
    faces: list
        A list of lists of face indices, or a flattened list of indices.
        If flat, then faceCounts must be provided
    faceCounts: list
        A list of the number of vertices per face. Defaults to None
    uvs: list or ndarray
        The Uvs for this mesh. Defaults to None
    uvFaces: list
        A list of lists of face indices, or a flattened list of indices.
        If flat, then faceCounts must be provided. Defaults to None
    normals: list or ndarray
        The Normals for this mesh. Defaults to None
    normFaces: list
        A list of lists of face indices, or a flattened list of indices.
        If flat, then faceCounts must be provided. Defaults to None
    name: str
        The name to give this mesh. Defaults to "polymsh"
    shapeSuffix: str
        The suffix to add to the shape of this mesh. Defaults to "Shape"
    transformSuffix: str
        The suffix to add to the transform of this mesh. Defaults to ""
    propDict: dict
        A dictionary of properties to add to the xform object
    ogawa : bool
        Whether to write to the Ogawa (True) or HDF5 (False) backend
    pBar : QProgressDialog, optional
        An optional progress dialog
    """
    if faceCounts is None:
        # All the faces are in list-of-list format
        # put them in index-count format
        faceCounts, faces = flattenFaces(faces)
        if uvFaces is not None:
            _, uvFaces = flattenFaces(uvFaces)
        if normFaces is not None:
            _, normFaces = flattenFaces(normFaces)

    faceCounts = mkSampleIntArray(faceCounts)
    faces = mkSampleIntArray(faces)

    if not isinstance(uvs, OV2fGeomParamSample):
        if uvFaces is not None and uvs is not None:
            uvs = mkUvSample(uvs, indexes=uvFaces)

    if not isinstance(normals, ON3fGeomParamSample):
        if normFaces is not None and normals is not None:
            normals = mkNormalSample(normals, indexes=normFaces)

    oarch = OArchive(str(outPath), ogawa)
    parent, opar, props, omesh, sch = None, None, None, None, None
    try:
        parent = oarch.getTop()
        opar = OXform(parent, str(name + transformSuffix))
        if propDict:
            props = opar.getSchema().getUserProperties()
            for k, v in six.iteritems(propDict):
                writeStringProperty(props, str(k), str(v), ogawa=ogawa)

        omesh = OPolyMesh(opar, str(name + shapeSuffix))

        if np is not None:
            points = np.array(points)
            if len(points.shape) == 2:
                points = points[None, ...]
        else:
            if not isinstance(points[0][0], (list, tuple)):
                points = [points]

        sch = omesh.getSchema()
        for i, frame in enumerate(points):
            pbPrint(pBar, message="Exporting Shape", val=i, maxVal=len(points))
            abcFrame = mkSampleVertexPoints(frame)
            setAlembicSample(sch, abcFrame, faceCounts, faces, uvs=uvs, normals=normals)

        pbPrint(pBar, message="Done Exporting")
    finally:
        # Make sure all this gets deleted so the file is freed
        del parent, opar, props, omesh, sch


# Simplex format specific stuff
def getSmpxArchiveData(abcPath):
    """Read and return the low level relevant data from a simplex alembic

    Parameters
    ----------
    abcPath : str
        The path to the .smpx file

    Returns
    -------
    : IArchive
        An opened Alembic IArchive object handle
    : IPolyMesh
        An Alembic Mesh handle
    : str
        The json definition string
    """
    if not os.path.isfile(str(abcPath)):
        raise IOError("File does not exist: " + str(abcPath))
    iarch = IArchive(str(abcPath))  # because alembic hates unicode
    top, par, abcMesh = [None] * 3
    try:
        top = iarch.getTop()
        par = top.children[0]
        par = IXform(top, par.getName())
        abcMesh = par.children[0]
        abcMesh = IPolyMesh(par, abcMesh.getName())
        # I *could* come up with a generic property reader
        # but it's useless for me at this time
        sch = par.getSchema()
        props = sch.getUserProperties()
        jsString = readStringProperty(props, "simplex")

    except Exception:  # pylint: disable=broad-except
        # ensure that the .smpx file is released
        iarch, top, par, abcMesh = [None] * 4
        raise

    # Must return the archive, otherwise it gets GC'd
    return iarch, abcMesh, jsString


def readSmpx(path, pBar=None):
    """Read and return the raw alembic vertex/face data in the flat alembic style

    Parameters
    ----------
    abcPath : str
        The path to the .smpx file
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : str
        The simplex definition string
    : [int, ...] or np.array
        The number of vertices per face
    : [[(float*3), ...], ...] or np.array
        The vertex positions per shape
    : [int, ...] or np.array
        The flat indexes per face
    : [(float*2), ...] or np.array or None
        The UV's
    : [int, ...] or np.array
        The flat indexes per uv-face
    """
    iarch, abcMesh, jsString = getSmpxArchiveData(path)
    try:
        faces, counts = getStaticMeshArrays(abcMesh)
        verts = getSampleArray(abcMesh, pBar=pBar)
        uvs = getUvArray(abcMesh)
        uvFaces, _ = getFlatUvFaces(abcMesh)
    finally:
        del iarch, abcMesh
    return jsString, counts, verts, faces, uvs, uvFaces


def buildSmpx(
    outPath,
    points,
    faces,
    jsString,
    name,
    faceCounts=None,
    uvs=None,
    uvFaces=None,
    ogawa=True,
    pBar=None,
):
    """
    Build a simplex output from raw data

    Parameters
    ----------
    outPath: str
        The output path for the alembic file
    points: list or ndarray
        The list or array of points. Single multiple frames supported
    faces: list
        A list of lists of face indices, or a flattened list of indices.
        If flat, then faceCounts must be provided
    jsString : str
        The simplex definition string
    name: str
        The name to give this mesh
    faceCounts: list
        A list of the number of vertices per face. Defaults to None
    uvs: list or ndarray
        The Uvs for this mesh. Defaults to None
    uvFaces: list
        A list of lists of face indices, or a flattened list of indices.
        If flat, then faceCounts must be provided. Defaults to None
    ogawa : bool
        Whether to write to the Ogawa (True) or HDF5 (False) backend
    pBar : QProgressDialog, optional
        An optional progress dialog
    """
    buildAbc(
        outPath,
        points,
        faces,
        faceCounts=faceCounts,
        uvs=uvs,
        uvFaces=uvFaces,
        name=name,
        shapeSuffix="",
        transformSuffix="",
        propDict=dict(simplex=jsString),
        ogawa=ogawa,
        pBar=pBar,
    )


def buildAlembicArchiveData(path, name, jsString, ogawa):
    """Set up an output alembic archive with a mesh ready for writing

    Parameters
    ----------
    path : str
        The output file path
    name : str
        The name of the system
    jsString : str
        The simplex definition string
    ogawa : bool
        Whether to open in Ogawa (True) or HDF5 (False) mode

    Returns
    -------
    : OArchive
        The opened alembic output archive
    : OPolyMesh
        The mesh to write the shape data to

    """
    arch = OArchive(str(path), ogawa)
    par, props, abcMesh = [None] * 3
    try:
        par = OXform(arch.getTop(), str(name))
        props = par.getSchema().getUserProperties()
        writeStringProperty(props, "simplex", jsString, ogawa=ogawa)
        abcMesh = OPolyMesh(par, str(name))
    except Exception:
        arch, par, props, abcMesh = [None] * 4
        raise
    return arch, abcMesh


def readFalloffData(abcPath):
    """Load the relevant data from a simplex alembic

    Parameters
    ----------
    abcPath : str
        Path to the .smpx file

    """
    if not os.path.isfile(str(abcPath)):
        raise IOError("File does not exist: " + str(abcPath))
    iarch = IArchive(str(abcPath))  # because alembic hates unicode
    top, par, systemSchema, foPropPar, foProp = [None] * 5
    try:
        top = iarch.getTop()
        par = top.children[0]
        par = IXform(top, par.getName())
        systemSchema = par.getSchema()
        props = systemSchema.getUserProperties()
        foDict = {}
        try:
            foPropPar = props.getProperty("falloffs")
        except KeyError:
            pass
        else:
            nps = foPropPar.getNumProperties()
            for i in range(nps):
                foProp = foPropPar.getProperty(i)
                fon = foProp.getName()
                fov = foProp.getValue()  # imath.FloatArray
                fov = list(fov) if np is None else np.array(fov)
                foDict[fon] = fov
    finally:
        iarch, top, par, systemSchema, foPropPar, foProp = [None] * 6

    return foDict
