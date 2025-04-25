import imath
import ctypes
import numpy as np
from typing import TypeVar, Type


NTYPEDICT: dict[type, type] = {
    ctypes.c_bool: bool,
    ctypes.c_byte: np.int8,
    ctypes.c_double: np.float64,
    ctypes.c_float: np.float32,
    ctypes.c_long: np.int32,
    ctypes.c_short: np.int16,
    ctypes.c_ubyte: np.uint8,
    ctypes.c_ulong: np.uint32,
    ctypes.c_ushort: np.uint16,
}

# fmt: off
TYPEDICT: dict[type, tuple[list[int], type, str]] = {
    imath.BoolArray:           ([],      ctypes.c_bool,   'array'),
    imath.DoubleArray:         ([],      ctypes.c_double, 'array'),
    imath.FloatArray:          ([],      ctypes.c_float,  'array'),
    imath.IntArray:            ([],      ctypes.c_long,   'array'),
    imath.ShortArray:          ([],      ctypes.c_short,  'array'),
    imath.SignedCharArray:     ([],      ctypes.c_byte,   'array'),
    imath.UnsignedCharArray:   ([],      ctypes.c_ubyte,  'array'),
    imath.UnsignedIntArray:    ([],      ctypes.c_ulong,  'array'),
    imath.UnsignedShortArray:  ([],      ctypes.c_ushort, 'array'),

    imath.Box2dArray:          ([2, 2],  ctypes.c_double, 'array'),
    imath.Box2fArray:          ([2, 2],  ctypes.c_float,  'array'),
    imath.Box2iArray:          ([2, 2],  ctypes.c_long,   'array'),
    imath.Box2sArray:          ([2, 2],  ctypes.c_short,  'array'),
    imath.Box3dArray:          ([2, 3],  ctypes.c_double, 'array'),
    imath.Box3fArray:          ([2, 3],  ctypes.c_float,  'array'),
    imath.Box3iArray:          ([2, 3],  ctypes.c_long,   'array'),
    imath.Box3sArray:          ([2, 3],  ctypes.c_short,  'array'),
    imath.C3cArray:            ([3],     ctypes.c_byte,   'array'),
    imath.C3fArray:            ([3],     ctypes.c_float,  'array'),
    imath.C4cArray:            ([4],     ctypes.c_byte,   'array'),
    imath.C4fArray:            ([4],     ctypes.c_float,  'array'),
    imath.M22dArray:           ([2, 2],  ctypes.c_double, 'array'),
    imath.M22fArray:           ([2, 2],  ctypes.c_float,  'array'),
    imath.M33dArray:           ([3, 3],  ctypes.c_double, 'array'),
    imath.M33fArray:           ([3, 3],  ctypes.c_float,  'array'),
    imath.M44dArray:           ([4, 4],  ctypes.c_double, 'array'),
    imath.M44fArray:           ([4, 4],  ctypes.c_float,  'array'),
    imath.QuatdArray:          ([4],     ctypes.c_double, 'array'),
    imath.QuatfArray:          ([4],     ctypes.c_float,  'array'),
    imath.V2dArray:            ([2],     ctypes.c_double, 'array'),
    imath.V2fArray:            ([2],     ctypes.c_float,  'array'),
    imath.V2iArray:            ([2],     ctypes.c_long,   'array'),
    imath.V2sArray:            ([2],     ctypes.c_short,  'array'),
    imath.V3dArray:            ([3],     ctypes.c_double, 'array'),
    imath.V3fArray:            ([3],     ctypes.c_float,  'array'),
    imath.V3iArray:            ([3],     ctypes.c_long,   'array'),
    imath.V3sArray:            ([3],     ctypes.c_short,  'array'),
    imath.V4dArray:            ([4],     ctypes.c_double, 'array'),
    imath.V4fArray:            ([4],     ctypes.c_float,  'array'),
    imath.V4iArray:            ([4],     ctypes.c_long,   'array'),
    imath.V4sArray:            ([4],     ctypes.c_short,  'array'),

    imath.Color4cArray2D:      ([4],     ctypes.c_byte,   'array2d'),
    imath.Color4fArray2D:      ([4],     ctypes.c_float,  'array2d'),
    imath.DoubleArray2D:       ([],      ctypes.c_double, 'array2d'),
    imath.FloatArray2D:        ([],      ctypes.c_float,  'array2d'),
    imath.IntArray2D:          ([],      ctypes.c_long,   'array2d'),

    imath.DoubleMatrix:        ([],      ctypes.c_double, 'matrix'),
    imath.FloatMatrix:         ([],      ctypes.c_float,  'matrix'),
    imath.IntMatrix:           ([],      ctypes.c_long,   'matrix'),

    imath.Box2d:               ([2, 2],  ctypes.c_double, 'box'),
    imath.Box2f:               ([2, 2],  ctypes.c_float,  'box'),
    imath.Box2i:               ([2, 2],  ctypes.c_long,   'box'),
    imath.Box2s:               ([2, 2],  ctypes.c_short,  'box'),
    imath.Box3d:               ([2, 3],  ctypes.c_double, 'box'),
    imath.Box3f:               ([2, 3],  ctypes.c_float,  'box'),
    imath.Box3i:               ([2, 3],  ctypes.c_long,   'box'),
    imath.Box3s:               ([2, 3],  ctypes.c_short,  'box'),

    imath.Line3d:              ([2, 3],  ctypes.c_double, 'line'),
    imath.Line3f:              ([2, 3],  ctypes.c_float,  'line'),

    imath.Color3c:             ([3],     ctypes.c_byte,   ''),
    imath.Color3f:             ([3],     ctypes.c_float,  ''),
    imath.Color4c:             ([4],     ctypes.c_byte,   ''),
    imath.Color4f:             ([4],     ctypes.c_float,  ''),
    imath.M22d:                ([2, 2],  ctypes.c_double, ''),
    imath.M22dRow:             ([2],     ctypes.c_double, 'row'),
    imath.M22f:                ([2, 2],  ctypes.c_float,  ''),
    imath.M22fRow:             ([2],     ctypes.c_float,  'row'),
    imath.M33d:                ([3, 3],  ctypes.c_double, ''),
    imath.M33dRow:             ([3],     ctypes.c_double, 'row'),
    imath.M33f:                ([3, 3],  ctypes.c_float,  ''),
    imath.M33fRow:             ([3],     ctypes.c_float,  'row'),
    imath.M44d:                ([4, 4],  ctypes.c_double, ''),
    imath.M44dRow:             ([4],     ctypes.c_double, 'row'),
    imath.M44f:                ([4, 4],  ctypes.c_float,  ''),
    imath.M44fRow:             ([4],     ctypes.c_float,  'row'),
    imath.Quatd:               ([4],     ctypes.c_double, ''),
    imath.Quatf:               ([4],     ctypes.c_float,  ''),
    imath.Shear6d:             ([6],     ctypes.c_double, ''),
    imath.Shear6f:             ([6],     ctypes.c_float,  ''),
    imath.V2d:                 ([2],     ctypes.c_double, ''),
    imath.V2f:                 ([2],     ctypes.c_float,  ''),
    imath.V2i:                 ([2],     ctypes.c_long,   ''),
    imath.V2s:                 ([2],     ctypes.c_short,  ''),
    imath.V3c:                 ([3],     ctypes.c_byte,   ''),
    imath.V3d:                 ([3],     ctypes.c_double, ''),
    imath.V3f:                 ([3],     ctypes.c_float,  ''),
    imath.V3i:                 ([3],     ctypes.c_long,   ''),
    imath.V3s:                 ([3],     ctypes.c_short,  ''),
    imath.V4c:                 ([4],     ctypes.c_byte,   ''),
    imath.V4d:                 ([4],     ctypes.c_double, ''),
    imath.V4f:                 ([4],     ctypes.c_float,  ''),
    imath.V4i:                 ([4],     ctypes.c_long,   ''),
    imath.V4s:                 ([4],     ctypes.c_short,  ''),
}
# fmt: on

# Define the in-memory structures of the python objects
# I'm *GUESSING* on most of the types here, so they could be refined
# in the future if required

# Here's hoping these structs don't change with different versions
# of python or imath


class PyImoObj(ctypes.Structure):
    _fields_ = [
        ("refcount", ctypes.c_ssize_t),  # from the PyObject c struct
        ("typeptr", ctypes.c_void_p),  # from the PyObject c struct
        ("unknown1", ctypes.c_ssize_t),  # Seems always -48 for some reason
        ("unknown2", ctypes.c_ssize_t),  # Seems always 0
        ("unknown3", ctypes.c_ssize_t),  # Seems always 0
        ("dataptr", ctypes.c_void_p),  # pointer to the PyImoDataObj
    ]


class PyImoDataObj(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_ssize_t),  # Some kind of type ID?
        ("unknown1", ctypes.c_ssize_t),  # Seems always 0
        ("dataptr", ctypes.c_void_p),  # Pointer to the allocated memory
        # There's MORE data after this, like the row/column count
        # and some other pointers. But I don't need them
        # Plus, there are some edge cases with the different types
        # like rows or bounding boxes
    ]


PyImoObjPtr = ctypes.POINTER(PyImoObj)
PyImoDataObjPtr = ctypes.POINTER(PyImoDataObj)


def _getImoPointer(imo, extra: str) -> int:
    """Get the memory address to the actual imath data

    Args:
        imo (imath object): The imath object to inspect
        extra (str): The metadata of this current type

    Returns:
        int: The memory address to the actual data
    """
    # This is a scary function
    # I found this stuff out by trial and error
    pyStruct = ctypes.cast(id(imo), PyImoObjPtr).contents
    if extra == "box":
        # I'm guessing that since the bounding box data is a known
        # size, they just put it directly into the structure
        # And the data is stored where the dataptr would be.
        # So I can just add the pyStruct.dataptr and the memory offset
        # of the PyImoDataObj.dataptr to get memory address of the box
        return pyStruct.dataptr + PyImoDataObj.dataptr.offset

    pyImoStruct = ctypes.cast(pyStruct.dataptr, PyImoDataObjPtr).contents
    return pyImoStruct.dataptr


def _link(imo) -> tuple[np.ndarray, int]:
    """ Build a numpy object that's referencing the same memory
    as the given imath object

    Args:
        imo (imath object): The imath object to build a link to

    Returns:
        np.ndarray: The numpy array
        int: The pointer to the memory address where the data lives
    """
    size, cdata, extra = TYPEDICT[type(imo)]
    if extra == "array":
        shape = [len(imo)] + size
    elif extra == "array2d":
        shape = list(imo.size()) + size
    elif extra == "matrix":
        shape = [imo.rows(), imo.columns()] + size
    elif extra in ("box", "line"):
        shape = size
    else:
        shape = [len(imo)]

    for s in shape[::-1]:
        cdata = cdata * s  # type: ignore

    ptr = _getImoPointer(imo, extra)
    ctypearray = cdata.from_address(ptr)
    nparray = np.ctypeslib.as_array(ctypearray)
    return nparray, ptr


def imathToNumpy(imo) -> np.ndarray:
    """Copy an imath object into a numpy array

    Args:
        imo (imath object): The imath object to convert

    Returns:
        np.ndarray: A copy of the imath object as a numpy array
    """
    gcarray, _ptr = _link(imo)
    return np.copy(gcarray)


T = TypeVar("T")


def numpyToImath(npo: np.ndarray, imtype: Type[T]) -> T:
    """Convert a numpy array to the given imath type

    Args:
        npo (array like): An object that can be cast to a numpy array
        imtype (type): The imath type to convert to

    Returns:
        imathObj: An instantiated imtype object with the numpy data loaded into it
    """
    size, cdata, extra = TYPEDICT[imtype]
    npo = np.asarray(npo, dtype=NTYPEDICT[cdata])
    if extra == "array":
        assert npo.ndim == len(size) + 1
        imo = imtype(len(npo))  # type: ignore
    elif extra in ("matrix", "array2d"):
        assert npo.ndim == 2 + len(size)
        imo = imtype(*npo.shape[:2])
    else:
        imo = imtype()

    tret, _ptr = _link(imo)
    np.copyto(tret, npo)
    return imo


def _test():
    """A quick test for all this crazy stuff"""

    # By default the bounding box objects are set to
    # The min/max for their types
    box3dnp = np.empty((2, 3), dtype=np.float64)
    box3dnp[0] = imath.DBL_MAX
    box3dnp[1] = imath.DBL_MIN

    box3fnp = np.empty((2, 3), dtype=np.float32)
    box3fnp[0] = imath.FLT_MAX
    box3fnp[1] = imath.FLT_MIN

    box3fanp = np.empty((5, 2, 3), dtype=np.float32)
    box3fanp[:] = box3fnp

    # M44fArray
    eyes = np.zeros((13, 4, 4), dtype=np.float32)
    eyes[:] = np.eye(4, dtype=np.float32)

    # Line3f
    line = np.zeros((2, 3), dtype=np.float32)
    line[1, 0] = 1.0

    # M33fRow
    im = imath.M33f()
    nm = np.eye(3, dtype=np.float32)

    # equivalent to an np.empty(3, 5)
    # so I have to set the values manually
    dubm = imath.DoubleMatrix(3, 5)
    tt = 0.0
    for i in range(3):
        row = dubm[i]
        for j in range(5):
            row[j] = tt
            tt += 1.0

    # fmt: off
    eqpairs = [
        (imath.V3dArray(11), np.zeros((11, 3))),
        (imath.M44fArray(13), eyes),
        (imath.V3d(), np.zeros(3)),
        (imath.Color4cArray2D(5, 7), np.zeros((5, 7, 4), dtype=np.int8)),
        (imath.Box3fArray(5), box3fanp),
        (imath.Box3d(), box3dnp),
        (imath.Box3f(), box3fnp),
        (imath.FloatArray(13), np.zeros((13), dtype=np.float32)),
        (imath.Line3f(), line),
        (im[1], nm[1]),
        (dubm, np.arange(15, dtype=float).reshape((3, 5))),
    ]
    # fmt: on

    for imo, chk in eqpairs:
        nv = imathToNumpy(imo)
        assert nv.dtype == chk.dtype
        assert np.all(nv == chk)

        imtype = type(imo)
        _size, _cdata, extra = TYPEDICT[imtype]
        if extra != "row":  # Can't directly build row objects
            _iv = numpyToImath(chk, imtype)
