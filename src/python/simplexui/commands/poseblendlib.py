import numpy as np

# I could have used the Scipy rotations library, but it doeosn't deal
# with ndim arrays of quaternions.


def positve_scalar(q: np.ndarray) -> np.ndarray:
    """Ensure the scalar value of an array of quaternions is positive"""
    shape = q.shape
    q = q.reshape((-1, 4))
    q[q[:, 3] < 0] *= -1
    return q.reshape(shape)


def outer(q: np.ndarray) -> np.ndarray:
    """Do the outer product of an array of quaternions with itself"""
    return q[..., None] * q[..., None, :]  # broadcast to do the outer products


def inverse_quats(q: np.ndarray) -> np.ndarray:
    """Get the inverses of the given unit quaternions"""
    ret = q.copy()
    ret[..., :-1] *= -1
    return ret


def norm_quats(q: np.ndarray) -> np.ndarray:
    """Normalize the given quaternions and flip any whose scalar component
    is negative
    """
    return positive_scalar(q / np.linalg.norm(q, axis=-1, keepdims=True))


def mul_quats(q1, q2):
    """Quaternion multiplication of two arrays

    Follows the convention that the right hand is applied "first"
    Like row-major transformation matrices
    """
    x1, y1, z1, w1 = q1[..., 0], q1[..., 1], q1[..., 2], q1[..., 3]
    x2, y2, z2, w2 = q2[..., 0], q2[..., 1], q2[..., 2], q2[..., 3]

    w = w2 * w1 - x2 * x1 - y2 * y1 - z2 * z1
    x = w2 * x1 + x2 * w1 + y2 * z1 - z2 * y1
    y = w2 * y1 - x2 * z1 + y2 * w1 + z2 * x1
    z = w2 * z1 + x2 * y1 - y2 * x1 + z2 * w1

    return np.stack((x, y, z, w), axis=-1)


def quaternion_pow(q: np.ndarray, n: np.ndarray):
    """Exponentiate unit quaternions
    Could also be thought of as slerping from the unit quaternion to the
    given quaternions

    Args:
        q (np.array[..., 4]): An array of quaternions
        n (np.array[..., 0]): An array of weights broadcastable to the shape
            of the quaternion array

    Returns:
        np.array[..., 4]: An array of exponentiated quaternions
    """
    w = np.clip(q[..., -1], -1.0, 1.0)
    v = q[..., :-1]

    theta = np.arccos(w)
    sin_theta = np.sin(theta)

    # Broadcast n to shape of theta
    n = np.broadcast_to(n, theta.shape)

    # Scale the rotation angle
    new_theta = n * theta
    new_w = np.cos(new_theta)

    # Fall back to a linear approximation for small angles
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(sin_theta > 1e-8, np.sin(new_theta) / sin_theta, n)

    new_v = v * scale[..., np.newaxis]

    result = np.concatenate([new_v, new_w[..., np.newaxis]], axis=-1)
    return result


def sum_weighted_quat_poses(
    restPose: np.ndarray,  # (N, 4) float
    targets: np.ndarray,  # (T, N, 4) float
    weights: np.ndarray,  # T float
    levels: np.ndarray,  # T int
) -> np.ndarray:  # (N, 4) float
    """Perform a "weighted sum" of target poses of quaternions with multiple
    levels. Each level is calculated individually, then multiplied in order
    to get the final output.

    This assumes Scalar (W) Last formatted quaternions

    This uses some interesting math that I don't fully understand. But the idea
    came from a NASA paper on the topic.

    Apparently if you sum a bunch of the outer products of quaternions with
    themselves, and then take the largest eigenvector of the resulting 4x4
    matrix, that eigenvector is (in some sense) the average of those quaternions.

    The naiive idea of an average is the sum divided by the count. So if you
    multiply an average value by the count, you should get back the sum.

    So if I take this "average" of quaternions and do a "multiplication" by the
    count, I should get back something that looks like a "sum" of the quaternions

    And to do "multiplication by the count", I just extrapolate the quaternion
    by slerping it to that count.

    This may not be "correct", but it sure seems to behave like I want it to.
    And that's all that matters for this application.

    Args:
        restPose (np.array[N, 4]): An array of quaternions
        targets (np.array[T, N, 4]): An array of target poses of quaternions
        weights (np.array[T]): The weight of each target
        levels (np.array[T]): The level of each target

    Returns:
        np.array[N, 4]: An array of quaternions
    """
    targets = norm_quats(targets)
    restPose = norm_quats(restPose)

    # Get the existing levels, and how many poses are at each level
    exlev, counts = np.unique(levels, return_counts=True)
    s_exlev = np.argsort(exlev)
    exlev = exlev[s_exlev]
    counts = counts[s_exlev]

    # Get the targets in the space of the rest pose
    restInv = inverse_quats(restPose)
    relTargets = mul_quats(targets, restInv[None])

    # Apply the weights to all the targets
    slerped = quaternion_pow(relTargets, weights[..., None])

    # Get the outer product of all the quaternions
    # and sum them by level
    outs = outer(slerped)
    levelEigs = np.zeros((exlev[-1] + 1, len(restPose), 4, 4))
    np.add.at(levelEigs, levels, outs)
    levelEigs = levelEigs[exlev]

    # Get largest eigenvalue for each matrix
    # This represents the *average* of each level
    evals, evecs = np.linalg.eig(levelEigs)
    mvals = np.argmax(np.abs(evals), axis=-1)[..., None, None]
    averages = np.take_along_axis(evecs, mvals, axis=evecs.ndim - 1).squeeze(axis=-1)
    averages = norm_quats(averages)

    # Take each level's pose to the power of its count
    sums = quaternion_pow(averages, counts[:, None])
    sums = norm_quats(sums)

    # Finally multiply the poses together on top of the rest pose
    qret = restPose.copy()
    for x in sums:
        qret = mul_quats(x, qret)

    return qret
