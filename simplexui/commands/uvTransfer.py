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

# pylint: disable=invalid-name
from __future__ import absolute_import, division, print_function

import six
from six.moves import range, zip

try:
    import numpy as np
except ImportError:
    pass


INF = float("inf")
EPS = 1e-7


########################
# Mean Value Coords
########################


def _lerp(idx, corners, p):
    # If I'm here, I know that p lies on the line
    # between the corners at idx and idx+1.
    # Return the lerp value
    ip = (idx + 1) % len(corners)
    c1 = corners[idx]
    c2 = corners[ip]
    base = c1 - c2
    proj = np.dot(p - c2, base)
    b = proj / (base**2).sum()
    ret = np.zeros(len(corners))
    ret[idx] = b
    ret[ip] = 1.0 - b
    return ret


def mvc(corners, p, tol=EPS):
    """Get the Mean Value Coordinates of a point p in the polygon defined by corners

    Parameters
    ----------
    corners : [int, ...]
        A list of corner indices
    p : np.array
        The array of points
    tol : float
        A small tolerance value, defaulting to the global EPS

    Returns
    -------
    : list
        The normalized list of barycentric weights for this point in the polygon

    """
    spokes = corners - p
    spokeLens = (spokes * spokes).sum(axis=1)

    # Check if p is on top of a vertex
    for i, v in enumerate(spokeLens):
        if v < tol:
            bary = np.zeros(len(corners))
            bary[i] = 1.0
            return bary

    rspokes = np.roll(spokes, -1, axis=0)
    areas = np.cross(spokes, rspokes) * 0.5
    dots = (spokes * rspokes).sum(axis=1)

    for i, v in enumerate(areas):
        if v < tol and dots[i] < 0.0:
            return _lerp(i, corners, p)

    spokeLens = spokeLens**0.5
    rspokeLens = np.roll(spokeLens, -1)
    t = areas / (spokeLens * rspokeLens + dots)
    rawWeights = (np.roll(t, 1) + t) / spokeLens
    return rawWeights / sum(rawWeights)


def mmvc(rawFaces, points, samples, uvToFace, tol=EPS):
    """Multi-MeanValueCoords
        Get the MVC's of many points over many faces using numpy

    Parameters
    ----------
    rawFaces : [[int, ...], ...]
        A list of face index lists
    points : np.array
        A numpy array of uv points
    samples : np.array
        A numpy array of points to get the barycentric coords for
    uvToFace : {int: [int, ...], ...}
        A dictionary of UV indices to a list of Face Indices
    tol : float
        A small tolerance value, defaulting to the global EPS

    Returns
    -------
    : {fc: (wh, barys)}
        A dictionary of face counts to a tuple containing the indices of the face indices
        checked, and the barycentric coords

    """
    uvIdxs, faceIdxs = sorted(zip(*list(uvToFace.items())))
    uvIdxs = np.array(uvIdxs)
    faces = [rawFaces[fi] for fi in faceIdxs]
    faceLens = np.array([len(i) for i in faces])
    fcs = np.unique(faceLens)

    out = {}
    for fc in fcs:
        wh = np.where(faceLens == fc)[0]
        cIdxs = np.array([faces[i] for i in wh])
        barys = np.zeros(cIdxs.shape)
        qIdxs = uvIdxs[wh]
        out[fc] = (qIdxs, barys)  # edit barys in-place

        # cornerses is a [f, fc, 2] array
        # where f is num of faces, fc is verts per face, and 2 because uv is 2d
        # pts is [f, 2] array where f is num faces
        cornerses = points[cIdxs]
        pts = samples[qIdxs]

        # Get the "spokes" from the query point to the face corners
        # and get their squared lengths
        spokes = cornerses - pts[:, None, :]
        spokeLens2 = (spokes * spokes).sum(axis=-1)

        # Handle any samples that are directly on top of a corner
        # (where the spoke length is zero)
        zeros = np.any(spokeLens2 < tol, axis=1)
        onPoint = np.where(zeros)
        offPoint = np.where(~zeros)
        if onPoint[0].size:
            pIdxs = spokeLens2[onPoint].argmin(axis=1)
            barys[onPoint, pIdxs] = 1.0

        if not offPoint[0].size:
            continue

        # Ignore those points that have already been computed
        idxs = offPoint[0]
        spokes = spokes[offPoint]
        spokeLens2 = spokeLens2[offPoint]

        # Get the signed area of each triangle created by the spokes
        # and the dot product for the angle between each
        rspokes = np.roll(spokes, -1, axis=1)
        areas = np.cross(spokes, rspokes) * 0.5
        dots = (spokes * rspokes).sum(axis=-1)

        # Handle any samples that are directly on an edge between
        # two corners. (Where the triangle area is 0, and the
        # dot product is negative)
        aareas = abs(areas)
        zeros = aareas < tol
        ndots = dots < 0.0
        zn = zeros & ndots
        toLerp = np.any(zn, axis=-1)
        onEdge = np.where(toLerp)
        offEdge = np.where(~toLerp)
        if onEdge[0].size:
            subIdx = idxs[onEdge]
            pIdxs = zn[onEdge].argmax(axis=-1)
            xIdxs = (pIdxs + 1) % fc

            ppIdxs = cIdxs[subIdx, pIdxs]
            xpIdxs = cIdxs[subIdx, xIdxs]

            cp = pts[subIdx]
            pp = points[ppIdxs]
            xp = points[xpIdxs]

            bases = pp - xp
            diff = cp - xp
            proj = (bases * diff).sum(axis=-1)
            b = proj / (bases**2).sum(axis=1)
            mb = 1.0 - b
            barys[subIdx, pIdxs] = b
            barys[subIdx, xIdxs] = mb

        if not offEdge[0].size:
            continue

        idxs = idxs[offEdge]
        dots = dots[offEdge]
        areas = areas[offEdge]
        spokeLens2 = spokeLens2[offEdge]
        spokeLens = spokeLens2**0.5
        rspokeLens = np.roll(spokeLens, -1, axis=1)

        t = areas / (spokeLens * rspokeLens + dots)
        rawWeights = (np.roll(t, -1, axis=1) + t) / spokeLens
        b = rawWeights / rawWeights.sum(axis=1)[..., None]
        barys[idxs] = b

    ret = {}
    for qIdxs, barys in six.itervalues(out):
        for qi, b in zip(qIdxs, barys):
            ret[qi] = (uvToFace[qi], b)

    return ret


########################
# Sweep algorithm
########################


def triArea(a, b, c):
    """Use the cross-ish-product to find the area of the triangle
        Depending on the winding, the area could be positive or negative

    Parameters
    ----------
    a : [float, float, float]
        The first point
    b : [float, float, float]
        The second point
    c : [float, float, float]
        The third point

    Returns
    -------
    : float
        The area of the triangle

    """
    return (a[0] * (c[1] - b[1]) + b[0] * (a[1] - c[1]) + c[0] * (b[1] - a[1])) / 2.0


def pointInTri(p, a, b, c, tol=EPS):
    """Check that the point is inside the triangle

    Parameters
    ----------
    p : [float, float, float]
        The point to check is inside the triangle
    a : [float, float, float]
        The first point of the triangle
    b : [float, float, float]
        The second point of the triangle
    c : [float, float, float]
        The third point of the triangle
    tol : float
        A small tolerance value, defaulting to the global EPS

    Returns
    -------
    : bool
        Whether the point is inside the given triangle

    """
    area = abs(triArea(a, b, c))
    chis = abs(triArea(p, b, c)) + abs(triArea(a, p, c)) + abs(triArea(a, b, p))
    return abs(area - chis) < tol


def sweep(qPoints, uvs, tris, pBar=None):
    """Get what triangle each query point is inside

    Runs a sweep-line algorithm to check for points in triangles.
    Imagine a uv layout, and a bunch of points on the layout.
    Now imagine a vertical line sweeping across the uv plane from the left
    to the right. The sorted u-values of certain properties then handled
    one-by-one.

    The algorithm keeps track of what triangles the vertical line is currently intersecting.

    * This is done by storing the min and max u-values for each triangle.
    * If the u-value encountered is the min for a tri, that tri is added to the list
    * If the u-value encountered is the max for a tri, that tri is removed from the list

    Then, each time a query point is encountered, it only has to check the intersection list

    Parameters
    ----------
    qPoints : np.array
        The points to get barycentric coordinates of
    uvs : np.array
        The UVs we're searching
    tris : np.array
        The Nx3 array of triangle indices
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : {int: int, ...}
        A dictionary of out[pointIndex] = triIndex
    : set()
        A set containing the pointIndexes that weren't found in a triangle

    """
    tpts = uvs[tris]  # [tIdx, abc, xy]

    allmxs, allmns = tpts.max(axis=1), tpts.min(axis=1)
    ymxs, ymns = allmxs[:, 1], allmns[:, 1]
    mxs, mns = allmxs[:, 0], allmns[:, 0]
    qpx = qPoints[:, 0]
    qpSIdxs, mxSIdxs, mnSIdxs = np.argsort(qpx), np.argsort(mxs), np.argsort(mns)
    qpSIdx, mxSIdx, mnSIdx = 0, 0, 0
    qpIdx, mxIdx, mnIdx = qpSIdxs[qpSIdx], mxSIdxs[mxSIdx], mnSIdxs[mnSIdx]
    qp, mx, mn = qpx[qpIdx], mxs[mxIdx], mns[mnIdx]

    out = {}
    missing = set()

    if pBar is not None:
        pBar.setValue(0)
        allVals = len(qpSIdxs) + len(mxSIdxs) + len(mnSIdxs)
        pBar.setRange(0, allVals)
        pBar.setLabelText("Sweeping ...")
        from Qt.QtWidgets import QApplication

        QApplication.processEvents()

    # skip any triangles to the left of the first query point
    # The algorithm will stop once we hit the last query point
    skip = [qp > m for m in mxs]
    activeTris = [False for _ in mxs]  # For fast membership testing
    atSet = set()  # For fast iteration

    while True:
        if pBar is not None:
            cVal = qpSIdx + mnSIdx + mxSIdx
            if cVal % 1283 == 0:  # Just a random prime
                pBar.setValue(cVal)
                pBar.setLabelText("Sweeping ...\n{0}/{1}".format(cVal, allVals))
                QApplication.processEvents()
                if pBar.wasCanceled():
                    raise RuntimeError("Cancelled!")

        if mn <= mx and mn <= qp:
            # Always add triangles first if possible
            aTriIdx = mnSIdxs[mnSIdx]
            if not activeTris[aTriIdx] and not skip[aTriIdx]:
                activeTris[aTriIdx] = True
                atSet.add(aTriIdx)

            mnSIdx += 1
            if mnSIdx != len(mnSIdxs):
                mnIdx = mnSIdxs[mnSIdx]
                mn = mns[mnIdx]
            else:
                mn = mxs[mxSIdxs[-1]] + 1

        elif qp <= mx:
            # Check query points between adding and removing
            qPoint = qPoints[qpIdx]
            yv = qPoint[1]
            # A linear search is faster than more complex collections here
            for t in atSet:
                if ymns[t] <= yv <= ymxs[t]:
                    a, b, c = uvs[tris[t]]
                    if pointInTri(qPoint, a, b, c):
                        out[qpIdx] = t
                        break
            else:
                missing.add(qpIdx)

            qpSIdx += 1
            if qpSIdx == len(qpSIdxs):
                break
            qpIdx = qpSIdxs[qpSIdx]
            qp = qpx[qpIdx]

        else:
            # always remove triangles last
            aTriIdx = mxSIdxs[mxSIdx]
            if activeTris[aTriIdx] and not skip[aTriIdx]:
                activeTris[aTriIdx] = False
                atSet.remove(aTriIdx)

            mxSIdx += 1
            if mxSIdx != len(mxSIdxs):
                mxIdx = mxSIdxs[mxSIdx]
                mx = mxs[mxIdx]

    return out, missing


########################
# Triangulation
########################


def inBox(point, mxs, mns):
    """Check if a point is inside the bounding box

    Parameters
    ----------
    point : np.array
        A 3d point
    mxs : np.array
        The max values of all the coordinates per axis
    mns : np.array
        The min values of all the coordinates per axis

    Returns
    -------
    : bool
        Whether the point is in the given bounding box

    """
    return np.all(point <= mxs) and np.all(point >= mns)


def _isEar(a, b, c, polygon, tol=EPS):
    """Check if the points a,b,c of the polygon could be their own triangle"""
    signedArea = triArea(a, b, c)

    # Check that the triange is wound the correct way.
    if signedArea > 0:
        return False

    # Check that the triangle has non-zero area
    # we already know the area is negative from above
    if -signedArea < tol:
        return False

    # Check that none of the other points in the polygon are contained in triangle
    for p in polygon:
        if p not in (a, b, c):
            if pointInTri(p, a, b, c, tol=tol):
                return False
    return True


def earclip(idxs, verts):
    """Simple earclipping algorithm
        For a polygon with n points it will return n-2 triangles.

    Parameters
    ----------
    idxs : [int, ...]
        The indices that make up a polygon
    verts : np.array
        All the UV positions

    Returns
    -------
    : [[int, int, int], ...]
        A list of triangle indices

    """
    earVerts = []
    tris = []
    idxs = list(idxs)
    polygon = [tuple(verts[i]) for i in idxs]

    numPts = len(polygon)
    for i in range(numPts):
        prev = polygon[i - 2]
        cur = polygon[i - 1]
        nxt = polygon[i]
        if _isEar(prev, cur, nxt, polygon):
            earVerts.append(cur)

    while earVerts and numPts >= 3:
        ear = earVerts.pop()
        i = polygon.index(ear)
        pi, ni = i - 1, (i + 1) % numPts

        prevPt = polygon[pi]
        nxtPt = polygon[ni]
        tris.append((idxs[pi], idxs[i], idxs[ni]))

        polygon.pop(i)
        idxs.pop(i)
        numPts -= 1
        if numPts > 3:
            prePrePt = polygon[i - 2]
            nxtNxtPt = polygon[(i + 1) % numPts]

            groups = [
                (prePrePt, prevPt, nxtPt, polygon),
                (prevPt, nxtPt, nxtNxtPt, polygon),
            ]

            for group in groups:
                p = group[1]
                if _isEar(*group):
                    if p not in earVerts:
                        earVerts.append(p)
                elif p in earVerts:
                    earVerts.remove(p)
    return tris


def triangulateUVs(faces, uvs):
    """Take a set of uvFaces and uv points, and triangulate it

    Parameters
    ----------
    faces : [[int, ...], ...]
        A uv face structure
    uvs : np.array
        The uv positions

    Returns
    -------
    : np.array
        A Nx3 array of uv indexes making triangles
    : [int, ...]
        A list where the index is the triangle index, and the value is the face index
    : {(int, int): int, ...}
        A dictionary of border edge pairs to border faces

    """
    uvs = np.array(uvs)
    triMap = []
    tris = []
    borderFaceMap = {}
    # Build the naiive triangulation
    # And get the borders while I'm looping
    for f, face in enumerate(faces):
        for i in range(2, len(face)):
            triMap.append(f)
            tris.append((face[0], face[i - 1], face[i]))

        for i in range(len(face)):
            ep = (face[i - 1], face[i])
            if ep[0] > ep[1]:
                ep = (ep[1], ep[0])
            if ep in borderFaceMap:
                borderFaceMap.pop(ep)
            else:
                borderFaceMap[ep] = f

    tris = np.array(tris)
    tuvs = uvs[tris]

    # Get the area using a 2d-pseudo-cross-product
    a = tuvs[:, 0] - tuvs[:, 1]
    b = tuvs[:, 2] - tuvs[:, 1]
    signedAreas = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]

    # Things with negative area are wound backwards in this case
    negArea = np.where(signedAreas < 0)

    # Do we need to retriangulate any of the polys
    retri = sorted(set(triMap[i] for i in negArea[0]))
    if retri:
        tris = tris.tolist()
        tmpFaceMap = {}
        # tmpFaceMap is only good while we re-triangulate
        # it has to be re-built after
        for t, f in enumerate(triMap):
            tmpFaceMap.setdefault(f, []).append(t)

        for f in retri[::-1]:
            good = earclip(faces[f], uvs)
            tidxs = tmpFaceMap[f]
            tris[tidxs[0] : tidxs[-1] + 1] = good
            triMap[tidxs[0] : tidxs[-1] + 1] = [f] * len(good)
        tris = np.array(tris)

    return tris, triMap, borderFaceMap


########################
# UV Transferring
########################

MISSING = {}


def cooSparseMul(M, v):
    """Multply the sparse matrix by the vector

    Parameters
    ----------
    M : SparseMatrix
        My own sparse matrix representation
    v : np.array
        A vector

    Returns
    -------
    : np.array
        The result of the multiplication
    """
    # Using scipy is at least 2x faster than the
    # pure numpy implementation. But even that
    # is about 5x faster than using a dense matrix
    try:
        from scipy import sparse
    except ImportError:
        # No scipy, use numpy
        # The numpy universal function (ufunc) .add.at()
        # makes this possible without any python looping
        row, col, val, shape = M
        v = v.swapaxes(0, -2)
        vshape = val.shape + tuple([1] * (len(v) - 1))
        val = val.reshape(vshape)
        out = np.zeros(shape[:1] + v.shape[1:])
        np.add.at(out, row, val * v[col])
        out = out.swapaxes(0, -2)
    else:
        row, col, val, shape = M
        spM = sparse.coo_matrix((val, (row, col)), shape=shape)
        spM = sparse.csr_matrix(spM)
        if len(v.shape) == 3:
            out = np.array([spM.dot(frm) for frm in v])
        else:
            out = spM.dot(v)
    return out


def getUvCorrelation(samples, points, faces, tol=0.0001, handleMissing=True, pBar=None):
    """Get the per-face correlation of the sample points in uv space.

    Parameters
    ----------
    samples : np.array
        The sample points
    points : np.array
        The background points
    faces : [[int, ...], ...]
        The Face list
    tol : float
        A small tolerance value, defaulting to the global EPS
    handleMissing :
         (Default value = True)
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : {idx: (idx, [float, ...]), ...}
        A dictionary from the sample index to a faceIdx/cornerWeights pair

    """
    tris, triMap, borderMap = triangulateUVs(faces, points)
    swept, missing = sweep(samples, points, tris, pBar=pBar)
    uvToFace = {uvI: triMap[tI] for uvI, tI in six.iteritems(swept)}
    # import __main__
    # __main__.__dict__.update(locals())
    # raise RuntimeError("STOPPIT")
    if pBar is not None:
        pBar.setValue(0)
        pBar.setRange(0, len(uvToFace))
        pBar.setLabelText("Calculate Mean Value Coords")
        from Qt.QtWidgets import QApplication

        QApplication.processEvents()

    # mvcDict = {}
    # for i, (uvIdx, faceIdx) in enumerate(uvToFace.iteritems()):
    # if pBar is not None:
    # pBar.setValue(i)
    # pBar.setLabelText("Calculate Mean Value Coords\n{0}/{1}".format(i, len(uvToFace)))
    # QApplication.processEvents()
    # uv = samples[uvIdx]
    # corners = points[faces[faceIdx]]
    # bary = mvc(corners, uv)
    # mvcDict[uvIdx] = (faceIdx, bary)

    mvcDict = mmvc(faces, points, samples, uvToFace)

    # find the closest border
    # Just use a brute-force search
    # ... for now

    if missing and handleMissing:
        if pBar is not None:
            pBar.setValue(0)
            pBar.setLabelText("Handle Missing")
            QApplication.processEvents()
        tol = tol**2
        bk = list(borderMap.keys())
        borders = np.array(bk)
        bStarts = points[borders[:, 0]]
        bEnds = points[borders[:, 1]]

        bDiff = bEnds - bStarts
        bLens2 = (bDiff * bDiff).sum(axis=1)
        for mIdx in missing:
            mp = samples[mIdx]
            dSquared = _mpCheck(bStarts, bDiff, bLens2, mp)
            minIdx = np.argmin(dSquared)
            if dSquared[mIdx] < tol:
                faceIdx = borderMap[bk[minIdx]]
                corners = points[faces[faceIdx]]
                bary = mvc(corners, mp)
                mvcDict[mIdx] = (faceIdx, bary)

    return mvcDict


def _mpCheck(a, d, dr2, pt):
    """Point to Multi-segment squared distance. Uses pre-computed values"""
    lerp = ((pt - a) * d).sum(axis=1) / dr2
    lerp = np.clip(lerp, 0, 1)
    xy = (lerp[:, None] * d) + a
    _dxy = xy - pt
    return (_dxy * _dxy).sum(axis=1)


def getVertCorrelation(
    sUvFaces, sUvs, tVertFaces, tUvFaces, tUvs, tol=0.0001, pBar=None
):
    """Build the vertex position correlation between two meshes
        by looking through UV-space. Handle combining multiple uvs
        per vertex, and having samples that live outside the coverage

    Parameters
    ----------
    sUvFaces : [[int, ...], ...]
        The source UVFace list
    sUvs : np.array
        The source UV positions
    tVertFaces : [[int, ...], ...]
        The target vertex face list
    tUvFaces : [[int, ...], ...]
        The target UV face list
    tUvs : np.array
        The target UV positions
    tol : float
        A small tolerance value, defaulting to the global EPS
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : {idx: (idx, [float, ...]), ...}
        A dictionary from the sample index to a faceIdx/cornerWeights pair
    """
    childUvToVert = {}
    cNumVerts = -1
    for vF, uvF in zip(tVertFaces, tUvFaces):
        for vIdx, uvIdx in zip(vF, uvF):
            cNumVerts = max(cNumVerts, vIdx)
            childUvToVert[uvIdx] = vIdx

    mvcUvDict = getUvCorrelation(tUvs, sUvs, sUvFaces, tol=tol, pBar=pBar)

    mvcVertDict = {}
    for uvIdx in range(len(tUvs)):
        if uvIdx not in mvcUvDict:
            continue
        mvcVertDict.setdefault(childUvToVert[uvIdx], []).append(mvcUvDict[uvIdx])

    missing = set(range(cNumVerts)) - six.viewkeys(mvcVertDict)
    if missing:
        import time

        v = time.time()
        print(
            "Missing correspondences found. Stored in uvTransfer.MISSING[{0}]".format(v)
        )
        MISSING[v] = missing

    return mvcVertDict


def applyTransfer(parVerts, parFaces, correlation, outputSize):
    """Given a vertex corelation, a driver, and driven points,
        Apply the driver deformation to the driven. This could be
        for one frame, or many frames

    Parameters
    ----------
    parVerts : np.array
        The "parent" vertex positions
    parFaces : [[int, ...], ...]
        The "parent" face list
    correlation : {int: [int, ...], ...}
        A dict correlatng the vertIdx to its possible correlations
    outputSize : (int, ...)
        A numpy output size tuple

    Returns
    -------
    : np.array
        The new vertex positions

    """
    if len(parVerts.shape) == 2:
        parVerts = parVerts[None, ...]

    rows, cols, vals = [], [], []
    for cVertIdx, corrPoss in six.iteritems(correlation):
        if len(corrPoss) == 1:
            pFaceIdx, bary = corrPoss[0]
        else:
            # pick the one with the highest sum-of-squares
            x = [sum(bary * bary) for _, bary in corrPoss]
            idx = x.index(max(x))
            pFaceIdx, bary = corrPoss[idx]

        rows.extend([cVertIdx] * len(bary))
        vals.extend(bary)
        cols.extend(parFaces[pFaceIdx])
    M = np.array(rows), np.array(cols), np.array(vals), (outputSize, parVerts.shape[-2])
    out = cooSparseMul(M, parVerts)
    return out


def uvTransfer(
    srcFaces,
    srcUvFaces,
    srcVerts,
    srcUvs,
    tarFaces,
    tarUvFaces,
    tarVerts,
    tarUvs,
    tol=0.0001,
    pBar=None,
):
    """A helper function that transfers pre-loaded data.
        The source data will be transferred onto the tar data

    Parameters
    ----------
    srcFaces : [[int, ...], ...]
        The source vertex face list
    srcUvFaces : [[int, ...], ...]
        The source uv face list
    srcUvs : np.array
        The source UV positions
    tarFaces : [[int, ...], ...]
        The target vertex face list
    tarUvFaces : [[int, ...], ...]
        The target uv face list
    tarUvs : np.array
        The Target UV Positions
    srcVerts : np.array
        The source Vertex positions
    tarVerts : np.array
        The target Vertex positions
    tol : float
        A small tolerance value, defaulting to the global EPS
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : np.array
        The new target vert positions

    """
    corr = getVertCorrelation(
        srcUvFaces, srcUvs, tarFaces, tarUvFaces, tarUvs, tol=tol, pBar=pBar
    )
    if pBar is not None:
        pBar.setValue(0)
        pBar.setLabelText("Apply Transfer")
        from Qt.QtWidgets import QApplication

        QApplication.processEvents()

    return applyTransfer(srcVerts, srcFaces, corr, len(tarVerts))


def uvTransferLoad(
    srcPath, tarPath, srcUvSet="default", tarUvSet="default", tol=0.0001, pBar=None
):
    """Transfer the shape from the source to the target through uv space
        Return the data needed to write out the result

    Parameters
    ----------
    srcPath : str
        The source mesh path (obj, abc, or smpx)
    tarPath : str
        The target mesh path (obj, abc, or smpx)
    srcUvSet : str
        The name of the uv set to use on the source
    tarUvSet : str
        The name of the uv set to use on the target
    tol : float
        A small tolerance value, defaulting to the global EPS
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------
    : np.array
        The target vertex positions
    : list
        The target vertex faces
    : np.array
        The target uvs
    : list
        The target uv faces

    """
    from . import alembicCommon as abc
    from .mesh import Mesh

    if srcPath.endswith(".abc") or srcPath.endswith(".smpx"):
        src = Mesh.loadAbc(srcPath, ensureWinding=False)
        srcVerts = abc.getSampleArray(abc.getMesh(srcPath))
    elif srcPath.endswith(".obj"):
        src = Mesh.loadObj(srcPath, ensureWinding=False)
        srcVerts = np.array(src.vertArray)

    if tarPath.endswith(".abc"):
        tar = Mesh.loadAbc(tarPath, ensureWinding=False)
    elif tarPath.endswith(".obj"):
        tar = Mesh.loadObj(tarPath, ensureWinding=False)

    srcFaces = src.faceVertArray
    srcUvFaces = src.uvFaceMap[srcUvSet]
    srcUvs = np.array(src.uvMap[srcUvSet])

    tarFaces = tar.faceVertArray
    tarUvFaces = tar.uvFaceMap[tarUvSet]
    tarUvs = np.array(tar.uvMap[tarUvSet])
    oldTarVerts = np.array(tar.vertArray)
    tarVerts = uvTransfer(
        srcFaces,
        srcUvFaces,
        srcVerts,
        srcUvs,
        tarFaces,
        tarUvFaces,
        oldTarVerts,
        tarUvs,
        tol=tol,
        pBar=pBar,
    )

    return tarVerts, tarFaces, tarUvs, tarUvFaces


def uvTransferFiles(
    srcPath,
    tarPath,
    outAbcPath,
    srcUvSet="default",
    tarUvSet="default",
    tol=0.0001,
    pBar=None,
):
    """Transfer the shape from the source to the target through uv space
        and write out the result

    Parameters
    ----------
    srcPath : str
        The source mesh path (obj, abc, or smpx)
    tarPath : str
        The target mesh path (obj, abc, or smpx)
    outAbcPath : str
        The path to the output .abc file
    srcUvSet : str
        The name of the uv set to use on the source
    tarUvSet : str
        The name of the uv set to use on the target
    tol : float
        A small tolerance value, defaulting to the global EPS
    pBar : QProgressDialog, optional
        An optional progress dialog

    Returns
    -------

    """
    from . import alembicCommon as abc

    tarVerts, tarFaces, tarUvs, tarUvFaces = uvTransferLoad(
        srcPath, tarPath, srcUvSet=srcUvSet, tarUvSet=tarUvSet, tol=tol, pBar=pBar
    )
    abc.buildAbc(outAbcPath, tarVerts, tarFaces, uvs=tarUvs, uvFaces=tarUvFaces)
