import numpy as np

# Relevant links:
#   - https://gist.github.com/nh2/bc4e2981b0e213fefd4aaa33edfb3893 (this code)
#   - http://stackoverflow.com/a/32244818/263061 (solution with scale)
#   - "Least-Squares Rigid Motion Using SVD" (no scale but easy proofs and explains how weights could be added)


# Rigidly (+scale) aligns two point clouds with know point-to-point correspondences
# with least-squares error.
# Returns (scale factor c, rotation matrix R, translation vector t) such that
#   Q = P*cR + t
# if they align perfectly, or such that
#   SUM over point i ( | P_i*cR + t - Q_i |^2 )
# is minimised if they don't align perfectly.
def umeyama(P, Q):
    assert P.shape == Q.shape
    n, dim = P.shape

    centeredP = P - P.mean(axis=0)
    centeredQ = Q - Q.mean(axis=0)

    C = np.dot(np.transpose(centeredP), centeredQ) / n

    V, S, W = np.linalg.svd(C)
    d = (np.linalg.det(V) * np.linalg.det(W)) < 0.0

    if d:
        S[-1] = -S[-1]
        V[:, -1] = -V[:, -1]

    R = np.dot(V, W)

    varP = np.var(a1, axis=0).sum()
    c = 1/varP * np.sum(S) # scale factor

    t = Q.mean(axis=0) - P.mean(axis=0).dot(c*R)

    return c, R, t


# Testing

np.set_printoptions(precision=3)

a1 = np.array([
  [0, 0, -1],
  [0, 0, 0],
  [0, 0, 1],
  [0, 1, 0],
  [1, 0, 0],
])

a2 = np.array([
  [0, 0, 1],
  [0, 0, 0],
  [0, 0, -1],
  [0, 1, 0],
  [-1, 0, 0],
])
a2 *= 2 # for testing the scale calculation
a2 += 3 # for testing the translation calculation


c, R, t = umeyama(a1, a2)
print "R =\n", R
print "c =", c
print "t =\n", t
print
print "Check:  a1*cR + t = a2  is", np.allclose(a1.dot(c*R) + t, a2)
err = ((a1.dot(c * R) + t - a2) ** 2).sum()
print "Residual error", err
