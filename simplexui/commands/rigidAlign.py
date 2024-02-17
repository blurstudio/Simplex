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

from six.moves import range

try:
    import numpy as np
except ImportError:
    pass


def rigidAlign(P, Q, iters=10):
    """Rigidly align meshes with matching vert order by a least-squares error.
    Uses a variation of an algorithm by Umeyama
    Relevant links:
    * https://gist.github.com/nh2/bc4e2981b0e213fefd4aaa33edfb3893 (this code)
    * http://stackoverflow.com/a/32244818/263061 (solution with scale)

    Parameters
    ----------
    P : np.array
        Static set of points
    Q : np.array
        Points to align with non-uniform scale
    iters : int
        The number of iterations (Defaults to 10)

    Returns
    -------
    : np.array
        The 4x4 transformation matrix that most closely aligns Q to P
    """
    # pylint:disable=invalid-name
    assert P.shape == Q.shape

    n, dim = P.shape
    assert dim == 3

    if iters <= 1:
        raise ValueError("Must run at least 1 iteration")

    # Get the centroid of each object
    Qm = Q.mean(axis=0)
    Pm = P.mean(axis=0)

    # Subtract out the centroid to get the basic aligned mesh
    cP = P - Pm  # centeredP
    cQRaw = Q - Qm  # centeredQ

    cQ = cQRaw.copy()
    cumulation = np.eye(3)  # build an accumulator for the rotation

    # Here, we find an approximate rotation and scaling, but only
    # keep track of the accumulated rotations.
    # Then we apply the non-uniform scale by comparing bounding boxes
    # This way we don't get any shear in our matrix, and we relatively
    # quickly walk our way towards a minimum
    for _ in range(iters):
        # Magic?
        C = np.dot(cP.T, cQ) / n
        V, S, W = np.linalg.svd(C)

        # Handle negative scaling
        d = (np.linalg.det(V) * np.linalg.det(W)) < 0.0
        if d:
            S[-1] = -S[-1]
            V[:, -1] = -V[:, -1]

        # build the rotation matrix for this iteration
        # and add it to the accumulation
        R = np.dot(V, W)
        cumulation = np.dot(cumulation, R.T)

        # Now apply the accumulated rotation to the raw point positions
        # Then grab the non-uniform scaling from the bounding box
        # And set up cQ for the next iteration
        cQ = np.dot(cQRaw, cumulation)
        sf = (cP.max(axis=0) - cP.min(axis=0)) / (cQ.max(axis=0) - cQ.min(axis=0))
        cQ = cQ * sf

    # Build the final transformation
    csf = cumulation * sf
    tran = Pm - Qm.dot(csf)
    outMat = np.eye(4)
    outMat[:3, :3] = csf
    outMat[3, :3] = tran
    return outMat
