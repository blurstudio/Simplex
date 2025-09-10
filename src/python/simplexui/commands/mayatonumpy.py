from maya import OpenMaya as om
import numpy as np
from ctypes import c_float, c_double, c_int, c_uint

# fmt: off
_CONVERT_DICT = {
    om.MPointArray:       (float, 4, c_double, om.MScriptUtil.asDouble4Ptr),
    om.MFloatPointArray:  (float, 4, c_float , om.MScriptUtil.asFloat4Ptr),
    om.MVectorArray:      (float, 3, c_double, om.MScriptUtil.asDouble3Ptr),
    om.MFloatVectorArray: (float, 3, c_float , om.MScriptUtil.asFloat3Ptr),
    om.MDoubleArray:      (float, 1, c_double, om.MScriptUtil.asDoublePtr),
    om.MFloatArray:       (float, 1, c_float , om.MScriptUtil.asFloatPtr),
    om.MIntArray:         (int  , 1, c_int   , om.MScriptUtil.asIntPtr),
    om.MUintArray:        (int  , 1, c_uint  , om.MScriptUtil.asUintPtr),
}
# fmt: on


def _swigConnect(mArray, count, util):
    """
    Use an MScriptUtil to build SWIG array that we can read from and write to.
    Make sure to get the MScriptUtil from outside this function, otherwise
    it may be garbage collected
    The _CONVERT_DICT holds {mayaType: (pyType, numComps, cType, ptrType)} where
            pyType: The type that is used to fill the MScriptUtil array.
            numComps: The number of components. So a double4Ptr would be 4
            cType: The ctypes type used to read the data
            ptrType: An unbound method on MScriptUtil to cast the pointer to the correct type
                    I can still call that unbound method by manually passing the usually-implicit
                    self argument (which will be an instance of MScriptUtil)
    """
    pyTyp, comps, ctp, ptrTyp = _CONVERT_DICT[type(mArray)]
    cc = count * comps
    util.createFromList([pyTyp()] * cc, cc)

    # passing util as 'self' to call the unbound method
    ptr = ptrTyp(util)
    mArray.get(ptr)

    if comps == 1:
        cdata = ctp * count
    else:
        # Multiplication follows some strange rules here
        # I would expect (ctype*3)*N to be an Nx3 array (ctype*3 repeated N times)
        # However, it gets converted to a 3xN array
        cdata = (ctp * comps) * count

    # int(ptr) gives the memory address
    cta = cdata.from_address(int(ptr))

    # This makes numpy look at the same memory as the ctypes array
    # so we can both read from and write to that data through numpy
    npArray = np.ctypeslib.as_array(cta)
    return npArray, ptr


def _swigConnectMatrix(mat, ctp):
    # With a matrix, you can just get the double[4][4] without an MScriptUtil
    ptr = mat.matrix
    cdata = ctp * 4 * 4

    # int(ptr) gives the memory address
    cta = cdata.from_address(int(ptr))

    # This makes numpy look at the same memory as the ctypes array
    # so we can both read from and write to that data through numpy
    npArray = np.ctypeslib.as_array(cta)
    return npArray, ptr


def mayaToNumpy(mArray):
    """Convert a maya array to a numpy array

    Parameters
    ----------
    ary : MArray
            The maya array to convert to a numpy array

    Returns
    -------
    : np.array :
            A numpy array that contains the data from mArray

    """
    if isinstance(mArray, om.MMatrix):
        npArray, _ = _swigConnectMatrix(mArray, c_double)
    elif isinstance(mArray, om.MFloatMatrix):
        npArray, _ = _swigConnectMatrix(mArray, c_float)
    else:
        util = om.MScriptUtil()
        count = mArray.length()
        npArray, _ = _swigConnect(mArray, count, util)
    return np.copy(npArray)


def numpyToMaya(ary, mType):
    """Convert a numpy array to a specific maya type array

    Parameters
    ----------
    ary : np.array
            The numpy array to convert to a maya array
    mType : type
            The maya type to convert to out of: MPointArray, MFloatPointArray, MVectorArray,
            MFloatVectorArray, MDoubleArray, MFloatArray, MIntArray, MUintArray

    Returns
    -------
    : mType :
            An array of the provided type that contains the data from ary

    """
    # Handle matrices separately
    if mType in (om.MMatrix, om.MFloatMatrix):
        ctp = c_double if mType == om.MMatrix else c_float
        if ary.shape != (4, 4):
            msg = "Numpy array must have the proper shape. For matrix types that shape must be (4, 4). Got {0}"
            raise ValueError(msg.format(ary.shape))
        tmpMat = mType()
        npArray, ptr = _swigConnectMatrix(tmpMat, ctp)
        np.copyto(npArray, ary)
        return mType(ptr)

    # Add a little shape checking
    comps = _CONVERT_DICT[mType][1]
    if comps == 1:
        if len(ary.shape) != 1:
            raise ValueError("Numpy array must be 1D to convert to the given maya type")
    else:
        if len(ary.shape) != 2:
            raise ValueError("Numpy array must be 2D to convert to the given maya type")
        if ary.shape[1] != comps:
            msg = "Numpy array must have the proper shape. Dimension 2 has size {0}, but needs size {1}"
            raise ValueError(msg.format(ary.shape[1], comps))
    count = ary.shape[0]
    tmpAry = mType(count)
    util = om.MScriptUtil()
    npArray, ptr = _swigConnect(tmpAry, count, util)
    np.copyto(npArray, ary)
    return mType(ptr, count)


# fmt: off
_NTYPE_DICT = {
    om.MFnNumericData.kInvalid: (om.MDataHandle.asDouble,  om.MDataHandle.setDouble),
    om.MFnNumericData.kFloat:   (om.MDataHandle.asDouble,  om.MDataHandle.setDouble),
    om.MFnNumericData.kDouble:  (om.MDataHandle.asDouble,  om.MDataHandle.setDouble),
    om.MFnNumericData.kByte:    (om.MDataHandle.asInt,     om.MDataHandle.setInt),
    om.MFnNumericData.kChar:    (om.MDataHandle.asChar,    om.MDataHandle.setChar),
    om.MFnNumericData.kShort:   (om.MDataHandle.asShort,   om.MDataHandle.setShort),
    om.MFnNumericData.kInt:     (om.MDataHandle.asInt,     om.MDataHandle.setInt),
    #om.MFnNumericData.kInt64:  (om.MDataHandle.asInt,     om.MDataHandle.setInt64),
    om.MFnNumericData.kAddr:    (om.MDataHandle.asInt,     om.MDataHandle.setInt),
    om.MFnNumericData.kLong:    (om.MDataHandle.asInt,     om.MDataHandle.setInt),
    om.MFnNumericData.kBoolean: (om.MDataHandle.asBool,    om.MDataHandle.setBool),

    om.MFnNumericData.k2Short:  (om.MDataHandle.asShort2,  om.MDataHandle.set2Short),
    om.MFnNumericData.k2Long:   (om.MDataHandle.asInt2,    om.MDataHandle.set2Int),
    om.MFnNumericData.k2Int:    (om.MDataHandle.asInt2,    om.MDataHandle.set2Int),
    om.MFnNumericData.k3Short:  (om.MDataHandle.asShort3,  om.MDataHandle.set3Short),
    om.MFnNumericData.k3Long:   (om.MDataHandle.asInt3,    om.MDataHandle.set3Int),
    om.MFnNumericData.k3Int:    (om.MDataHandle.asInt3,    om.MDataHandle.set3Int),
    om.MFnNumericData.k2Float:  (om.MDataHandle.asFloat2,  om.MDataHandle.set2Float),
    om.MFnNumericData.k2Double: (om.MDataHandle.asDouble2, om.MDataHandle.set2Double),
    om.MFnNumericData.k3Float:  (om.MDataHandle.asFloat3,  om.MDataHandle.set3Float),
    om.MFnNumericData.k3Double: (om.MDataHandle.asDouble3, om.MDataHandle.set3Double),
}

_DTYPE_DICT = {
    om.MFn.kPointArrayData:  (om.MFnPointArrayData,  om.MPointArray),
    om.MFn.kDoubleArrayData: (om.MFnDoubleArrayData, om.MDoubleArray),
    om.MFn.kFloatArrayData:  (om.MFnFloatArrayData,  om.MFloatArray),
    om.MFn.kIntArrayData:    (om.MFnIntArrayData,    om.MIntArray),
    om.MFn.kUInt64ArrayData: (om.MFnUInt64ArrayData, om.MPointArray),
    om.MFn.kVectorArrayData: (om.MFnVectorArrayData, om.MVectorArray),
}
# fmt: on


def getNumpyAttr(attrName):
    """Read attribute data directly from the plugs into numpy

    This function will read most numeric data types directly into numpy arrays
    However, some simple data types (floats, vectors, etc...) have api accessors
    that return python tuples. These will not be turned into numpy arrays.
    And really, if you're getting simple data like that, just use cmds.getAttr

    Parameters
    ----------
    attrName : str or om.MPlug
            The name of the attribute to get (For instance "pSphere2.translate", or "group1.pim[0]")
            Or the MPlug itself

    Returns
    -------
    : object :
            The numerical data from the provided plug. A np.array, float, int, or tuple

    """
    if isinstance(attrName, str):
        sl = om.MSelectionList()
        sl.add(attrName)
        plug = om.MPlug()
        sl.getPlug(0, plug)
    elif isinstance(attrName, om.MPlug):
        plug = attrName
    else:
        raise ValueError("AttrName is not a name or a plug")

    # First just check if the data is numeric
    mdh = plug.asMDataHandle()
    if mdh.isNumeric():
        # So, at this point, you should really just use getattr
        ntype = mdh.numericType()
        if ntype in _NTYPE_DICT:
            return _NTYPE_DICT[ntype][0](mdh)
        elif ntype == om.MFnNumericData.k4Double:
            NotImplementedError("Haven't implemented double4 access yet")
        else:
            raise RuntimeError(
                "I don't know how to access data from the given attribute"
            )
    else:
        # The data is more complex than a simple number.
        try:
            pmo = plug.asMObject()
        except RuntimeError as e:
            # raise a more descriptive error. And make sure to actually print the plug name
            raise RuntimeError(
                "I don't know how to access data from the given attribute"
            ) from e
        apiType = pmo.apiType()

        # A list of types that I can just pass to mayaToNumpy
        if apiType in _DTYPE_DICT:
            fn, dtype = _DTYPE_DICT[apiType]
            fnPmo = fn(pmo)
            ary = fnPmo.array()
            return mayaToNumpy(ary)

        elif apiType == om.MFn.kComponentListData:
            fnPmo = om.MFnComponentListData(pmo)
            mirs = []
            mir = om.MIntArray()
            for attrIndex in range(fnPmo.length()):
                fnEL = om.MFnSingleIndexedComponent(fnPmo[attrIndex])
                fnEL.getElements(mir)
                mirs.append(mayaToNumpy(mir))
            if not mirs:
                return np.array([], dtype=int)
            return np.concatenate(mirs)

        elif apiType == om.MFn.kMatrixData:
            fnPmo = om.MFnMatrixData(pmo)
            mat = fnPmo.matrix()
            return mayaToNumpy(mat)
        else:
            apiTypeStr = pmo.apiTypeStr()
            raise NotImplementedError(
                "I don't know how to handle {0} yet".format(apiTypeStr)
            )
    raise NotImplementedError("Fell all the way through")


def setNumpyAttr(attrName, value):
    """Write a numpy array directly into a maya plug

    This function will handle most numeric plug types.
    But for single float, individual point, etc.. types, consider using cmds.setAttr

    THIS DOES NOT SUPPORT UNDO

    Parameters
    ----------
    attrName : str or om.MPlug
            The name of the attribute to get (For instance "pSphere2.translate", or "group1.pim[0]")
            Or the MPlug itself
    value : int, float, tuple, np.array
            The correctly typed value to set on the attribute
    """
    if isinstance(attrName, str):
        sl = om.MSelectionList()
        sl.add(attrName)
        plug = om.MPlug()
        sl.getPlug(0, plug)
    elif isinstance(attrName, om.MPlug):
        plug = attrName
    else:
        raise ValueError("Data must be string or MPlug. Got {0}".format(type(attrName)))

    # First just check if the data is numeric
    mdh = plug.asMDataHandle()
    if mdh.isNumeric():
        # So, at this point, you should really just use setattr
        ntype = mdh.numericType()
        if ntype in _NTYPE_DICT:
            _NTYPE_DICT[ntype][1](mdh, *value)
            plug.setMObject(mdh.data())
        elif ntype == om.MFnNumericData.k4Double:
            NotImplementedError("Haven't implemented double4 access yet")
        else:
            raise RuntimeError("I don't know how to set data on the given attribute")
    else:
        # The data is more complex than a simple number.
        try:
            pmo = plug.asMObject()
        except RuntimeError as e:
            # raise a more descriptive error. And make sure to actually print the plug name
            raise RuntimeError(
                "I don't know how to access data from the given attribute"
            ) from e
        apiType = pmo.apiType()

        if apiType in _DTYPE_DICT:
            # build the pointArrayData
            fnType, mType = _DTYPE_DICT[apiType]
            fn = fnType()
            mPts = numpyToMaya(value, mType)
            dataObj = fn.create(mPts)
            plug.setMObject(dataObj)
            return

        elif apiType == om.MFn.kComponentListData:
            fnCompList = om.MFnComponentListData()
            compList = fnCompList.create()
            fnIdx = om.MFnSingleIndexedComponent()
            idxObj = fnIdx.create(om.MFn.kMeshVertComponent)
            mIdxs = numpyToMaya(value, om.MIntArray)
            fnIdx.addElements(mIdxs)
            fnCompList.add(idxObj)
            plug.setMObject(compList)
            return
        else:
            apiTypeStr = pmo.apiTypeStr()
            raise NotImplementedError(
                "I don't know how to handle {0} yet".format(apiTypeStr)
            )

    raise NotImplementedError("WTF? How did you get here??")


################################################################################


def test():
    import time
    from maya import cmds

    meshName = "pSphere1"
    bsName = "blendShape1"
    meshIdx = 0
    bsIdx = 0

    # A quick test showing how to build a numpy array
    # containing the deltas for a shape on a blendshape node
    numVerts = cmds.polyEvaluate(meshName, vertex=True)
    baseAttr = "{0}.it[{1}].itg[{2}].iti[6000]".format(bsName, meshIdx, bsIdx)
    inPtAttr = baseAttr + ".inputPointsTarget"
    inCompAttr = baseAttr + ".inputComponentsTarget"

    start = time.time()
    points = getNumpyAttr(inPtAttr)
    idxs = getNumpyAttr(inCompAttr)
    ret = np.zeros((numVerts, 4))
    ret[idxs] = points
    end = time.time()

    print("IDXS", idxs.shape)
    print("OUT", points.shape)
    print("RET", ret.shape)
    print("TOOK", end - start)


if __name__ == "__main__":
    test()
