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

# pylint: disable=unused-argument, too-many-locals
# pylint:disable=E0611,E0401

from __future__ import absolute_import, print_function

import json
from itertools import chain

import six
from six.moves import map, range, zip, zip_longest

from ..Qt.QtWidgets import QApplication
from .alembicCommon import buildSmpx, pbPrint, readSmpx

try:
    import numpy as np
except ImportError:
    np = None


def mergeCycles(groups):
    """Take a list of ordered items, and sort them so the last item of each list matches the first of the next list

    Then return the groups of lists mashed together
    For instance, with two cycles:
    +---------+------------------------------------------------------------+
    | input   | [(1, 2), (11, 12), (3, 1), (10, 11), (2, 3), (12, 10)]     |
    +---------+------------------------------------------------------------+
    | reorder | [[(1, 2), (2, 3), (3, 1)], [(10, 11), (11, 12), (12, 13)]] |
    +---------+------------------------------------------------------------+
    | output  | [[1, 2, 3], [10, 11, 12, 13]]                              |
    +---------+------------------------------------------------------------+

    Also, return whether the cycles merged form a single closed group

    Parameters
    ----------
    groups : [(int, int), ...]
        A list of pairs of integers

    Returns
    -------
    : [[int, ...], ...]
        The ordered cycles
    """
    groups = [list(g) for g in groups]
    heads = {g[0]: g for g in groups}
    tails = {g[-1]: g for g in groups}

    headGetter = lambda x: heads.get(x[-1])
    headSetter = lambda x, y: x + y[1:]

    tailGetter = lambda x: tails.get(x[0])
    tailSetter = lambda x, y: y + x[1:]

    searches = ((headGetter, headSetter), (tailGetter, tailSetter))

    out = []
    cycles = []
    while groups:
        g = groups.pop()
        del heads[g[0]]
        del tails[g[-1]]

        for getter, setter in searches:
            while True:
                adder = getter(g)
                if adder is None:
                    break
                g = setter(g, adder)
                del heads[adder[0]]
                del tails[adder[-1]]
                adder[:] = []
            groups = [x for x in groups if x]

        cycle = False
        if g[0] == g[-1]:
            g.pop()
            cycle = True
        cycles.append(cycle)
        out.append(g)
    return out, cycles


def grow(neigh, verts, exclude):
    """Grow the vertex set, also keeping track of which vertices to ignore for the next iteration

    Parameters
    ----------
    neigh : {int: [int, ...]}
        A dict mapping a vert index to a list of neighbor vert indices
    verts : set(int)
        A set of vert indices to grow
    exclude : set(int)
        A set of vert indices to ignore

    Returns
    -------
    : set(int)
        The newly grown vertices
    : set(int)
        ``exclude`` combined with ``verts``

    """
    grown = set()
    growSet = verts - exclude
    for v in growSet:
        grown.update(neigh[v])
    newGrown = grown - exclude
    newExclude = exclude | growSet
    return newGrown, newExclude


def buildHint(island, neigh, borders):
    """Find star points that are an even number of grows from an edge

    Parameters
    ----------
    island : [int, ...]
        A list of vertices as part of a mesh island
    neigh : {int: [int, ...]}
        The dictionary of vertex neighbors
    borders : set(int)
        A set of border vertices

    Returns
    -------
    : int
        The first star point encountered at an even grow from the given borders
    """
    borders = borders & island
    if not borders:
        # Well ... we don't have any good way of dealing with this
        # Best thing I can do is search for a point with the least
        # number of similar valences, and return that
        d = {}
        for v in island:
            d.setdefault(len(neigh[v]), []).append(v)

        dd = {}
        for k, v in six.iteritems(d):
            dd.setdefault(len(v), []).append(k)

        mkey = min(dd.keys())
        return d[dd[mkey][0]][0]

    exclude = set()
    while borders:
        borders, exclude = grow(neigh, borders, exclude)
        borders, exclude = grow(neigh, borders, exclude)
        for b in borders:
            if len(neigh[b]) != 4:
                return b
    return None


def partitionIslands(faces, neigh, pBar=None):
    """Find all groups of connected verts

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    neigh : {int: [int, ...]}
        The dict of vertex neighbors
    pBar : QProgressDialog or None
        An optional progress bar

    Returns
    -------
    : [set(int), ...]
        A list of sets of non-connected vertex islands
    """
    allVerts = set(chain.from_iterable(faces))
    islands = []
    count = float(len(allVerts))

    if pBar is not None:
        pBar.setValue(0)
        pBar.setMaximum(count)
        QApplication.processEvents()

    while allVerts:
        verts = set([allVerts.pop()])
        exclude = set()
        while verts:
            verts, exclude = grow(neigh, verts, exclude)
        islands.append(exclude)
        allVerts.difference_update(exclude)

        if pBar is not None:
            pBar.setValue(count - len(allVerts))
            QApplication.processEvents()

    return islands


def buildUnsubdivideHints(faces, neigh, borders, pBar=None):
    """Get one vertex per island that was part of the original mesh

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    neigh : {int: [int, ...]}
        The dict of vertex neighbors
    borders : set(int)
        A set of border vertices
    pBar : QProgressDialog or None
        An optional progress bar

    Returns
    -------
    : [int, ...]
        A list of star-points (one per island) to un-subdivide from
    """
    islands = partitionIslands(faces, neigh, pBar=pBar)
    hints = []

    if pBar is not None:
        pBar.setValue(0)
        pBar.setMaximum(len(islands))
        QApplication.processEvents()

    for i, isle in enumerate(islands):
        if pBar is not None:
            pBar.setValue(i)
            QApplication.processEvents()
        hints.append(buildHint(isle, neigh, borders))

    hints = [h for h in hints if h is not None]
    return hints


def getFaceCenterDel(faces, eNeigh, hints, pBar=None):
    """Given a list of hint "keeper" points

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    eNeigh : {int: [int, ...]}
        The dict of vertex neighbors
    hints : [int, ...]
        A list of star-points (one per island) to un-subdivide from
    pBar : QProgressDialog or None
        An optional progress bar

    Returns
    -------
    : set(int)
        Centers of the original faces during a subdivision
    : bool
        Whether the operation failed(True) or not(False)
    """
    vertToFaces = {}
    vc = set()
    for i, face in enumerate(faces):
        for f in face:
            vertToFaces.setdefault(f, []).append(i)
            vc.add(f)

    count = len(vc)
    centers = set()
    midpoints = set()
    originals = set(hints)
    queue = set(hints)

    if pBar is not None:
        pBar.setValue(0)
        pBar.setMaximum(count)
        QApplication.processEvents()

    i = 0
    fail = False
    while queue:
        cur = queue.pop()
        if cur in midpoints:
            continue

        if pBar is not None:
            pBar.setValue(i)
            QApplication.processEvents()
            i += 2  # Add 2 because I *shouldn't* get any midpoints

        midpoints.update(eNeigh[cur])
        t = centers if cur in originals else originals

        for f in vertToFaces[cur]:
            nVerts = faces[f]

            if len(nVerts) != 4:
                fail = True
                continue

            curFaceIndex = nVerts.index(cur)

            half = int(len(nVerts) / 2)
            diag = nVerts[curFaceIndex - half]

            isOrig = diag in originals
            isCtr = diag in centers
            if not isOrig and not isCtr:
                t.add(diag)
                queue.add(diag)
            elif (
                (isCtr and t is originals)
                or (isOrig and t is centers)
                or (diag in midpoints)
            ):
                fail = True

    return centers, fail


def getBorders(faces):
    """Get the indices of verts along the borders of a mesh

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces

    Returns
    -------
    : set(int)
        A set of border vertices
    """
    edgePairs = set()
    for face in faces:
        for f in range(len(face)):
            edgePairs.add((face[f], face[f - 1]))
    borders = set()
    for ep in edgePairs:
        if (ep[1], ep[0]) not in edgePairs:
            borders.update(ep)
    return borders


def buildEdgeDict(faces):
    """Build a dictionary of un-ordered neighboring vertices along edges

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces

    Returns
    -------
    : {int: set(int)}
        A dictionary of neighboring vertices along edges
    """
    edgeDict = {}
    for face in faces:
        for f in range(len(face)):
            ff = edgeDict.setdefault(face[f - 1], set())
            ff.add(face[f])
            ff.add(face[f - 2])
    return edgeDict


def buildNeighborDict(faces):
    """Build a structure to ask for edge and face neighboring vertices
        The returned neighbor list starts with an edge neighbor, and
        proceeds counter clockwise, alternating between edge and face neighbors
        Also, while I'm here, grab the border verts

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces

    Returns
    -------
    : {int: [[int, ...], ...]}
        A dictionary keyed from a vert index whose
            values are ordered cycles or fans
    : set(int)
        A set of vertices that are on the border
    """
    fanDict = {}
    edgeDict = {}
    for face in faces:
        for i in range(len(face)):
            fanDict.setdefault(face[i], []).append(face[i + 1 :] + face[:i])
            ff = edgeDict.setdefault(face[i - 1], set())
            ff.add(face[i])
            ff.add(face[i - 2])

    borders = set()
    out = {}
    for k, v in six.iteritems(fanDict):
        fans, cycles = mergeCycles(v)
        for f, c in zip(fans, cycles):
            if not c:
                borders.update((f[0], f[-1], k))
        out[k] = fans
    return out, edgeDict, borders


def _fanMatch(fan, uFan, dWings):
    """Twist a single fan so it matches the uFan if it can"""
    uIdx = uFan[0]
    for f, fIdx in enumerate(fan):
        dw = dWings.get(fIdx, [])
        if uIdx in dw:
            return fan[f:] + fan[:f]
    return None


def _align(neigh, uNeigh, dWings):
    """Twist all the neighs so they match the uNeigh"""
    out = []
    for uFan in uNeigh:
        for fan in neigh:
            fm = _fanMatch(fan, uFan, dWings)
            if fm is not None:
                out.append(fm)
                break
    return out


def buildLayeredNeighborDicts(faces, uFaces, dWings):
    """Build and align two neighbor dicts for both faces and uFaces
    This guarantees that the neighbors at the same index are analogous
    (ie. they go in the same direction)

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    uFaces : [[int, ...], ...]
        The list of lists of vertex indices making up un-subdivided faces
    dWings : ???
        ???

    Returns
    -------

    """
    neighDict, edgeDict, borders = buildNeighborDict(faces)
    uNeighDict, uEdgeDict, uBorders = buildNeighborDict(uFaces)

    assert (
        borders >= uBorders
    ), "Somehow the unsubdivided borders contain different vIdxs"

    for i, (k, uNeigh) in enumerate(six.iteritems(uNeighDict)):
        neighDict[k] = _align(neighDict[k], uNeigh, dWings)

    return neighDict, uNeighDict, edgeDict, uEdgeDict, borders


def _findOldPositionBorder(
    faces,
    uFaces,
    verts,
    uVerts,
    neighDict,
    uNeighDict,
    edgeDict,
    uEdgeDict,
    borders,
    vIdx,
    computed,
):
    """Find the position of the un-subdivided mesh if the vertex was on the border"""
    nei = neighDict[vIdx][0]
    nei = [i for i in nei if i in borders]
    assert len(nei) == 2, "Found multi border, {}".format(nei)
    uVerts[vIdx] = 2 * verts[vIdx] - ((verts[nei[0]] + verts[nei[1]]) / 2)
    computed.add(vIdx)


def _findOldPositionSimple(
    faces,
    uFaces,
    verts,
    uVerts,
    neighDict,
    uNeighDict,
    edgeDict,
    uEdgeDict,
    vIdx,
    computed,
):
    """Find the position of the un-subdivided mesh if the vertex has at least 4 neighbors.
    Updates uVerts in-place
    """
    neigh = neighDict[vIdx][0]

    eTest = edgeDict[vIdx]
    e = [p for p in neigh if p in eTest]
    f = [p for p in neigh if p not in eTest]

    es = verts[e].sum(axis=0)
    fs = verts[f].sum(axis=0)

    n = len(e)
    term1 = verts[vIdx] * (n / (n - 3.0))
    term2 = es * (4 / (n * (n - 3.0)))
    term3 = fs * (1 / (n * (n - 3.0)))
    vk = term1 - term2 + term3

    uVerts[vIdx] = vk
    computed.add(vIdx)


def _findOldPosition3Valence(
    faces,
    uFaces,
    verts,
    uVerts,
    neighDict,
    uNeighDict,
    edgeDict,
    uEdgeDict,
    vIdx,
    computed,
):
    """Find the position of the un-subdivided mesh if the vertex has exactly 3 neighbors
    Updates uVerts in-place. It is possible for this to fail.

    Returns
    -------
    : bool
        Whether an update happened
    """
    neigh = neighDict[vIdx][0]
    uNeigh = uNeighDict[vIdx][0]

    eTest = edgeDict[vIdx]
    eNeigh = [n for n in neigh if n in eTest]
    fNeigh = [n for n in neigh if n not in eTest]

    ueTest = uEdgeDict[vIdx]
    ueNeigh = [n for n in uNeigh if n in ueTest]
    # ufNeigh = [n for n in uNeigh if n not in ueTest]

    intr = computed.intersection(ueNeigh)
    if intr:
        # Easy valence 3 case. I only need
        # The computed new neighbor
        # The midpoint on the edge to that neighbor
        # The "face" verts neighboring the midpoint

        # Get the matching subbed an unsubbed neighbor indexes
        uNIdx = intr.pop()
        nIdx = eNeigh[ueNeigh.index(uNIdx)]

        # Get the "face" verts next to the subbed neighbor
        xx = neigh.index(nIdx)
        fnIdxs = (neigh[xx - 1], neigh[(xx + 1) % len(neigh)])

        # Then compute
        # vk = 4*k1e - ke - k1fNs[0] - k1fNs[1]
        vka = uVerts[uNIdx] + verts[fnIdxs[0]] + verts[fnIdxs[1]]
        vkb = verts[nIdx] * 4
        uVerts[vIdx] = vkb - vka
        computed.add(vIdx)
        return True

    else:
        # The Hard valence 3 case. Made even harder
        # because the paper has a mistake in it

        # vk = 4*ejk1 + 4*ejpk1 - fjnk1 - fjpk1 - 6*fjk1 + sum(fik)
        # where k1 means subdivided mesh
        # where j means an index, jn and jp are next/prev adjacents
        # sum(fik) is the sum of all the points of the face that
        #     *aren't* the original, or edge-adjacent
        #     There could be more than 1 if an n-gon was subdivided
        #
        # I wonder: If it was a triangle that was subdivided, what
        # would sum(fik) because there are no verts that fit that
        # description.  I think this is a degenerate case

        # First, find an adjacent face on the unsub mesh that
        # is only missing the neighbors of the vIdx

        fnIdx = None
        fik = None
        fCtrIdx = None
        for x, v in enumerate(fNeigh):
            # working with neigh, but should only ever contain uNeigh indexes
            eTest = edgeDict[vIdx]
            origFace = set([n for n in neighDict[v][0] if n not in eTest])

            check = (origFace - set(ueNeigh)) - set([vIdx])
            if computed >= check:
                fCtrIdx = v
                fnIdx = x
                fik = sorted(list(check))
                break

        if fnIdx is None:
            # No possiblity found
            return False

        # Then apply the equation from above
        neighIdx = neigh.index(fCtrIdx)
        ejnk1 = neigh[(neighIdx + 1) % len(neigh)]
        ejpk1 = neigh[neighIdx - 1]
        fjnk1 = fNeigh[(fnIdx + 1) % len(fNeigh)]
        fjpk1 = fNeigh[fnIdx - 1]
        fjk1 = verts[fCtrIdx]
        sumFik = uVerts[fik].sum(axis=0)
        vk = 4 * ejnk1 + 4 * ejpk1 - fjnk1 - fjpk1 - 6 * fjk1 + sumFik
        uVerts[vIdx] = vk
        computed.add(vIdx)
        return True
    return False


def deleteCenters(meshFaces, uvFaces, centerDel, pBar=None):
    """Delete the given vertices and connected edges from a face representation
        to give a new representation.

    Parameters
    ----------
    meshFaces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    centerDel : set(int)
        A set of vertices to delete. These were the vertices added
        to the centers of the faces when subdividing.
    uvFaces : [[int, ...], ...]
        The list of lists of uv indices making up uvFaces
    pBar : QProgressDialog or None
        An optional progress bar

    Returns
    -------
    : [[int, ...], ...]
        The new list of faces of the mesh
    : [[int, ...], ...]
        The new list of uvfaces of the mesh
    : {int: (int, int)}
        A dict of a deleted edge-midpoint to its two existing neighbor verts
    : {int: (int, int)}
        A dict of a deleted uv edge-midpoint to its two existing neighbor uvs
    """
    # For each deleted index, grab the neighboring faces,
    # and twist the faces so the deleted index is first
    cds = set(centerDel)
    faceDelDict = {}
    uvDelDict = {}
    uvFaces = uvFaces or []
    for face, uvFace in zip_longest(meshFaces, uvFaces):
        fi = cds.intersection(face)
        # If we are a subdivided mesh, Then each face will have exactly one
        # vertex that is part of the deletion set
        if len(fi) != 1:
            raise ValueError("Found a face with an unrecognized connectivity")
        # Get that one vert
        idx = fi.pop()
        # Each face is a cycle. Rotate the cycle
        # so that idx is first in the list
        rv = face.index(idx)
        rFace = face[rv:] + face[:rv]
        faceDelDict.setdefault(idx, []).append(rFace)

        if uvFace is not None:
            rUVFace = uvFace[rv:] + uvFace[:rv]
            uvDelDict.setdefault(idx, []).append(rUVFace)

    newFaces = []
    nUVFaces = []
    wings = {}
    uvWings = {}

    if pBar is not None:
        pBar.setValue(0)
        pBar.setMaximum(len(faceDelDict))

    chk = -1
    for idx, rFaces in six.iteritems(faceDelDict):
        chk += 1
        if pBar is not None:
            pBar.setValue(chk)
            QApplication.processEvents()

        ruvFaces = uvDelDict.get(idx, [])
        # The faces are guaranteed to be in a single loop cycle
        # so I don't have to handle any annoying edge cases! Yay!
        faceEnds = {
            f[1]: (f[2], f[3], uvf) for f, uvf in zip_longest(rFaces, ruvFaces)
        }  # face ends

        end = rFaces[-1][-1]  # get an arbitrary face to start with
        newFace = []
        nUVFace = []
        while faceEnds:
            try:
                diag, nxt, uvf = faceEnds.pop(end)
            except KeyError:
                print("rFaces", rFaces)
                print("fe", faceEnds)
                raise
            if uvf is not None:
                try:
                    nUVFace.append(uvf[2])
                    uvWings.setdefault(uvf[1], []).append(uvf[2])
                    uvWings.setdefault(uvf[3], []).append(uvf[2])
                except IndexError:
                    print("UVF", uvf, chk)
                    raise

            newFace.append(diag)
            wings.setdefault(end, []).append(diag)
            wings.setdefault(nxt, []).append(diag)

            end = nxt
        newFaces.append(newFace)
        if nUVFace:
            nUVFaces.append(nUVFace)
    nUVFaces = nUVFaces or None

    return newFaces, nUVFaces, wings, uvWings


def fixVerts(
    faces,
    uFaces,
    verts,
    neighDict,
    uNeighDict,
    edgeDict,
    uEdgeDict,
    borders,
    pinned,
    pBar=None,
):
    """Given the faces, vertex positions, and the point indices that
        were created at the face centers for a subdivision step
        Return the faces and verts of the mesh from before the
        subdivision step. This algorithm doesn't handle UV's yet

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    verts : np.array
        The Nx3 array of vertices
    centerDel : set(int)
        A set of vertices to delete
    uFaces : [[int, ...], ...]
        The list of lists of vertex indices making up the
        un-subdivided faces. Not all numbers in the vert range are in this structure
    neighDict : {int: [int, ...]}
        The dictionary of vertex neighbors based on ``faces``
    uNeighDict : {int: [int, ...]}
        The dictionary of vertex neighbors based on ``uFaces``
    edgeDict : TODO
        Some kind of dictionary representing individual edges
    uEdgeDict : TODO
        Some kind of dictionary representing individual edges in the unsub mesh
    borders : set(int)
        The set of vertices along the borders
    pinned : set(int)
        The set of vertices that will not be moved by this process
    pBar : QProgressDialog or None
        An optional progress bar

    Returns
    -------
    : np.array
        An array of vertex positions
    """
    uVerts = verts.copy()
    uIdxs = sorted(list(set([i for i in chain.from_iterable(uFaces)])))

    v3Idxs = []
    # bowtie verts are pinned
    bowTieIdxs = []
    computed = set()
    i = 0
    if pBar is not None:
        pBar.setValue(0)
        pBar.setMaximum(len(uIdxs))

    for idx in uIdxs:
        if pBar is not None:
            pBar.setValue(i)
            QApplication.processEvents()
        if len(uNeighDict[idx]) > 1:
            bowTieIdxs.append(idx)
            i += 1
        elif idx in pinned:
            pass
        elif idx in borders:
            _findOldPositionBorder(
                faces,
                uFaces,
                verts,
                uVerts,
                neighDict,
                uNeighDict,
                edgeDict,
                uEdgeDict,
                borders,
                idx,
                computed,
            )
            i += 1
        elif sum(map(len, neighDict[idx])) > 6:  # if valence > 3
            _findOldPositionSimple(
                faces,
                uFaces,
                verts,
                uVerts,
                neighDict,
                uNeighDict,
                edgeDict,
                uEdgeDict,
                idx,
                computed,
            )
            i += 1
        else:
            v3Idxs.append(idx)

    updated = True
    while updated:
        updated = False
        rem = set()
        for idx in v3Idxs:
            up = _findOldPosition3Valence(
                faces,
                uFaces,
                verts,
                uVerts,
                neighDict,
                uNeighDict,
                edgeDict,
                uEdgeDict,
                idx,
                computed,
            )
            if not up:
                continue
            if pBar is not None:
                pBar.setValue(i)
                QApplication.processEvents()
            i += 1
            updated = True
            rem.add(idx)
        v3Idxs = list(set(v3Idxs) - rem)

    return uVerts


def getUVPins(faces, borders, uvFaces, uvBorders, pinBorders):
    """Find which uvBorders are also mesh borders

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    borders : set(int)
        The set of vertices along the borders
    uvFaces : [[int, ...], ...]
        The list of lists of uv indices making up uvFaces
    uvBorders : set(int)
        The set of vertices along the borders of uvs
    pinBorders : bool
        Whether to just pin all uv borders

    Returns
    -------
    : set(int)
        The vertex indices to pin
    """
    if uvFaces is None:
        return set()
    if pinBorders:
        return set(uvBorders)

    pinnit = set()
    for face, uvFace in zip(faces, uvFaces):
        for i in range(len(face)):
            f = face[i]
            pf = face[i - 1]

            uv = uvFace[i]
            puv = uvFace[i - 1]

            if not (f in borders and pf in borders):
                if uv in uvBorders and puv in uvBorders:
                    pinnit.add(puv)
                    pinnit.add(uv)

    return uvBorders & pinnit


def collapse(faces, verts, uvFaces, uvs):
    """Take a mesh representation with unused vertex indices, and remove those vertices

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
        The set of integers used here will be non-contiguous
    verts : np.array
        The N*3 array of vertices
    uvFaces : [[int, ...], ...]
        The list of lists of uv indices making up uvFaces
        The set of integers used here will be non-contiguous
    uvs : np.array
        The N*2 array of uvs

    Returns
    -------
    : [[int, ...], ...]
        The list of lists of vertex indices making up faces
        The set of integers used here will be contiguous
    : np.array
        The new N*3 array of vertices
    : [[int, ...], ...]
        The list of lists of uv indices making up uvFaces
        The set of integers used here will be non-contiguous
    : np.array
        The new N*2 array of uvs
    """
    vset = sorted(list(set(chain.from_iterable(faces))))
    nVerts = verts[vset]
    vDict = {v: i for i, v in enumerate(vset)}
    nFaces = [[vDict[f] for f in face] for face in faces]

    if uvFaces is not None:
        uvset = sorted(list(set(chain.from_iterable(uvFaces))))
        nUVs = uvs[uvset]
        uvDict = {v: i for i, v in enumerate(uvset)}
        nUVFaces = [[uvDict[f] for f in face] for face in uvFaces]
    else:
        nUVs = None
        nUVFaces = None

    return nFaces, nVerts, nUVFaces, nUVs


def getCenters(faces, hints=None, pBar=None):
    """Given a set of faces, find the face-center vertices from the subdivision

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    hints : set(int) or None
        An optional list of star points that were part of the original un-subdivided mesh
    pBar : QProgressDialog or None
        An optional progress bar

    Returns
    -------
    : set(int)
        The vertices that were added to the centers of the faces as part of the subdivision process
    """
    if pBar is not None:
        pBar.setLabelText("Crawling Edges")
        pBar.show()
        QApplication.processEvents()

    eNeigh = buildEdgeDict(faces)
    if hints is None:
        borders = getBorders(faces)
        hints = buildUnsubdivideHints(
            faces, eNeigh, borders, pBar=None
        )  # purposely no PBar
    centerDel, fail = getFaceCenterDel(faces, eNeigh, hints, pBar=pBar)
    assert not fail, "Could not detect subdivided topology with the provided hints"

    if pBar is not None:
        pBar.close()

    return centerDel


def unSubdivide(
    faces,
    verts,
    uvFaces,
    uvs,
    hints=None,
    repositionVerts=True,
    pinBorders=False,
    pBar=None,
):
    """Given a mesh representation (faces and vertices) remove the edges added
        by a subdivision, and optionally reposition the verts

    Parameters
    ----------
    faces : [[int, ...], ...]
        The list of lists of vertex indices making up faces
    verts : np.array
        The N*3 array of vertices
    uvFaces : [[int, ...], ...]
        The list of lists of uv indices making up uvFaces
    uvs : np.array
        The N*2 array of uvs
    hints : set(int) or None
        An optional list of star points that were part of the original un-subdivided mesh
    repositionVerts : bool
        Whether to also estimate the positions of the un-subdivided verts. Defaults to True
    pinBorders : bool
        Whether or not to pin the border vertices. Defaults to False
    pBar : QProgressDialog or None
        An optional progress bar

    Returns
    -------
    : [[vIdx ...], ...]
        The un-subdivided face structure
    : np.array
        The un-subdivided vertex positions
    : [[vIdx ...], ...] or None
        The un-subdivided uv-face structure if it exists
    : np.array or None
        The un-subdivided uvs if they exist
    """
    if pBar is not None:
        pBar.show()
        pBar.setLabelText("Finding Neighbors")
        QApplication.processEvents()

    eNeigh = buildEdgeDict(faces)

    if hints is None:
        if pBar is not None:
            pBar.show()
            pBar.setLabelText("Getting Hints")
            QApplication.processEvents()
        borders = getBorders(faces)
        hints = buildUnsubdivideHints(
            faces, eNeigh, borders, pBar=None
        )  # Purposely no PBar

    if pBar is not None:
        pBar.setLabelText("Crawling Edges")
        QApplication.processEvents()
    centerDel, fail = getFaceCenterDel(faces, eNeigh, hints, pBar=pBar)
    assert not fail, "Could not detect subdivided topology with the provided hints"

    if pBar is not None:
        pBar.setLabelText("Deleting Edges")
        QApplication.processEvents()
    uFaces, uUVFaces, dWings, uvDWings = deleteCenters(
        faces, uvFaces, centerDel, pBar=pBar
    )

    uVerts = verts
    uUVs = uvs
    if repositionVerts:
        # Handle the verts
        if pBar is not None:
            pBar.setLabelText("Building Correspondences")
            QApplication.processEvents()
        neighDict, uNeighDict, edgeDict, uEdgeDict, borders = buildLayeredNeighborDicts(
            faces, uFaces, dWings
        )
        pinned = set(borders) if pinBorders else []
        if pBar is not None:
            pBar.setLabelText("Fixing Vert Positions")
            QApplication.processEvents()
        uVerts = fixVerts(
            faces,
            uFaces,
            verts,
            neighDict,
            uNeighDict,
            edgeDict,
            uEdgeDict,
            borders,
            pinned,
            pBar=pBar,
        )

        # Handle the UVs
        if uvFaces is not None:
            (
                uvNeighDict,
                uUVNeighDict,
                uvEdgeDict,
                uvUEdgeDict,
                uvBorders,
            ) = buildLayeredNeighborDicts(uvFaces, uUVFaces, uvDWings)
            uvPinned = getUVPins(faces, borders, uvFaces, uvBorders, pinBorders)
            if pBar is not None:
                pBar.setLabelText("Fixing UV Positions")
                QApplication.processEvents()
            uUVs = fixVerts(
                uvFaces,
                uUVFaces,
                uvs,
                uvNeighDict,
                uUVNeighDict,
                uvEdgeDict,
                uvUEdgeDict,
                uvBorders,
                uvPinned,
                pBar=pBar,
            )

    rFaces, rVerts, rUVFaces, rUVs = collapse(uFaces, uVerts, uUVFaces, uUVs)

    if pBar is not None:
        pBar.close()

    return rFaces, rVerts, rUVFaces, rUVs


####################################################################
#                  Handle .smpx files here                         #
####################################################################


def _ussmpx(faces, verts, uvFaces, uvs, pBar=None):
    """Unsubdivide a simplex"""
    pbPrint(pBar, message="Finding Neighbors")
    eNeigh = buildEdgeDict(faces)

    pbPrint(pBar, message="Getting Hints")
    borders = getBorders(faces)
    hints = buildUnsubdivideHints(
        faces, eNeigh, borders, pBar=None
    )  # Purposely no PBar

    pbPrint(pBar, message="Crawling Edges")
    centerDel, fail = getFaceCenterDel(faces, eNeigh, hints, pBar=pBar)
    assert not fail, "Could not detect subdivided topology with the provided hints"

    pbPrint(pBar, message="Deleting Edges")
    uFaces, uUVFaces, _, _ = deleteCenters(faces, uvFaces, centerDel, pBar=pBar)

    pbPrint(pBar, message="Collapsing Indexes")
    uVerts = verts
    uUVs = uvs

    rFaces, rVerts, rUVFaces, rUVs = collapse(uFaces, uVerts, uUVFaces, uUVs)

    if pBar is not None:
        pBar.close()
    else:
        print("Done")

    return rFaces, rVerts, rUVFaces, rUVs


def _applyShapePrefix(shapePrefix, jsString):
    """Apply a prefix to the shape names.
    For XSI where shape names must be unique
    """
    if shapePrefix is not None:
        d = json.loads(jsString)
        if d["encodingVersion"] > 1:
            for shape in d["shapes"]:
                shape["name"] = shapePrefix + shape["name"]
        else:
            d["shapes"] = [shapePrefix + i for i in d["shapes"]]
        jsString = json.dumps(d)
    return jsString


def _unflattenFaces(flatFaces, counts):
    faces = []
    ptr = 0
    for c in counts:
        faces.append(flatFaces[ptr : ptr + c].tolist())
        ptr += c
    return faces


def unsubdivideSimplex(inPath, outPath, shapePrefix=None, pBar=None):
    """Unsubdivde a .smpx file on disk

    Parameters
    ----------
    inPath : str
        The input .smpx file path
    outPath : str
        The output .smpx file path
    shapePrefix : str or None
        An optional string to prefix the shape names with
    pBar : QProgressDialog or None
        An optional progress bar
    """
    if np is None:
        raise RuntimeError("Un-Subdivide requires numpy, and it is not available here")

    pbPrint(pBar, message="Loading smpx")
    jsString, counts, verts, flatFaces, uvs, flatUVFaces = readSmpx(inPath)
    jsString = _applyShapePrefix(shapePrefix, jsString)

    js = json.loads(jsString)
    name = js["systemName"]

    faces = _unflattenFaces(flatFaces, counts)
    uvFaces = None
    if flatUVFaces is not None:
        uvFaces = _unflattenFaces(flatUVFaces, counts)

    pbPrint(pBar, message="Unsubdividing")
    verts = verts.swapaxes(0, 1)
    uFaces, uVerts, uUVFaces, uUVs = _ussmpx(faces, verts, uvFaces, uvs, pBar=pBar)

    pbPrint(pBar, message="Exporting")
    buildSmpx(
        outPath,
        uVerts.swapaxes(0, 1),
        uFaces,
        jsString,
        name,
        uvs=uUVs,
        uvFaces=uUVFaces,
    )
