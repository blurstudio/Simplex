from __future__ import annotations
from typing import cast, Iterator

from .alembicCommon import getIArchive

from alembic.Abc import (
    IArchive,
    OArchive,
    IObject,
    OObject,
    IProperty,
    OProperty,
    OCompoundProperty,
    OScalarProperty,
    OArrayProperty,
    ICompoundProperty,
)


class AlembicWalker(object):
    """This class recursively walks an alembic hierarchy, copying
    all objects and properties along the way.

    It's written as a class to allow for overriding methods used in the
    copying process. To add extra decision making and archive mutation

    copy_alembic Takes input and output filepaths and kicks off the copy process
    copy_hierarchy takes input and output alembic objects and copies the hierarchy
        from the input to the output
    copy_object_properties copies the property data from one object to another.
    copy_property_data copies the the data from input to output

    make_obj_walk is the recursive generator function that walks the object hierarchy
        depth-first, and creates the empty output objects with the correct type metadata
        that copy_object_properties will fill
    make_prop_walk is the recursive generator function that walks the property hierarchy
        depth-first, and creates the empty output properties of the correct type that
        copy_property_data fills
    """

    @classmethod
    def make_prop_walk(
        cls,
        iPar: ICompoundProperty,
        oPar: OCompoundProperty,
        depth: int = 0,
        name: list[str] | None = None,
        debug: bool = False,
        *args,
        **kwargs,
    ) -> Iterator[tuple[IProperty, OProperty, int, list[str]]]:
        """Generator for depth-first iteration and duplication of the
        properties of an alembic object. Every input property is recreated with the
        same name and type as an output object, then yielded from the method

        You would override this method if you needed to add or remove certain properties
        from the objects when processing the input archive

        Arguments:
            iPar (ICompoundProperty): The parent input property whose sub-properties we will
                iterate over
            oPar (OCompoundProperty): The output property that will act as the container
                for all the newly created properties
            depth (int): The current depth of the hierarchy
            name (list): The full path-name of the current property. This is the name
                of all parent container properties as a list
            debug (bool): Whether to print the debug messages
            args/kwargs : Additional arguments that will get passed down the stack
                This saves you from having to override all methods to pass a single
                argument to the bottom of the call stack

        Yields:
            iProperty: An input property to copy sub-properties and values from
            oProperty: An output property to copy sub-properties and values to
            int: The current depth of the objects in the hierarchy
            list: The current path-name of the properties to be copied
        """
        name = name or []
        num = iPar.getNumProperties()
        pfx = "  " * depth
        for i in range(num):
            iProp = iPar.getProperty(i)
            nextName = name + [iProp.getName()]

            if iProp.isCompound():
                if debug:
                    print(pfx, iProp.getName())
                oProp = OCompoundProperty(oPar, iProp.getName(), iProp.getMetaData())
            elif iProp.isArray():
                if debug:
                    print(pfx, iProp.getName())
                oProp = OArrayProperty(
                    oPar, iProp.getName(), iProp.getDataType(), iProp.getMetaData()
                )
            else:
                if debug:
                    print(pfx, iProp.getName())
                oProp = OScalarProperty(
                    oPar, iProp.getName(), iProp.getDataType(), iProp.getMetaData()
                )

            yield iProp, oProp, depth, nextName
            if iProp.isCompound():
                iProp = cast(ICompoundProperty, iProp)
                oProp = cast(OCompoundProperty, oProp)

                for ip, op, d, nn in cls.make_prop_walk(
                    iProp, oProp, depth + 1, nextName, *args, debug=debug, **kwargs
                ):
                    yield ip, op, d, nn

    @classmethod
    def make_obj_walk(
        cls,
        iPar: IObject,
        oPar: OObject,
        depth: int = 0,
        debug: bool = False,
        *args,
        **kwargs,
    ) -> Iterator[tuple[IObject, OObject, int]]:
        """Generator for depth-first iteration and duplication over the
        objects in an alembic file. Every input object is recreated with the same
        name and metadata as an output object, then yielded from the method

        You would override this method if you needed to change the type of an
        object, change the output hierarchy, or skip certain objects when
        processing the input archive

        Arguments:
            iPar (iObject): The parent input object whose children we will
                iterate over
            oPar (oObject): The output object that will act as the parent
                for all the newly created duplicates of the iPar's children
            depth (int): The current depth of the hierarchy
            debug (bool): Whether to print the debug messages
            args/kwargs : Additional arguments that will get passed down the stack
                This saves you from having to override all methods to pass a single
                argument to the bottom of the call stack

        Yields:
            iObject: An object to copy properties from
            oObject: An object to copy properties to
            int: The current depth of the objects in the hierarchy
        """
        num = iPar.getNumChildren()
        pfx = "  " * depth
        for i in range(num):
            iChild = iPar.getChild(i)
            if debug:
                print(pfx, iChild.getName())
            oChild = OObject(oPar, iChild.getName(), iChild.getMetaData())

            yield iChild, oChild, depth
            for ic, oc, d in cls.make_obj_walk(
                iChild, oChild, depth + 1, *args, debug=debug, **kwargs
            ):
                yield ic, oc, d

    @classmethod
    def copy_time_sampling(
        cls, inProp: IProperty, outProp: OProperty, *args, **kwargs
    ) -> None:
        """Choose the output timeSampling corresponding to the input one

        Arguments:
            inProp (IProperty): The property to copy the time sampling from
            outProp (OProperty): The property to copy the time sampling to
            args/kwargs : Additional arguments that will get passed down the stack
                This saves you from having to override all methods to pass a single
                argument to the bottom of the call stack
        """
        iSampling = inProp.getTimeSampling()
        outProp.setTimeSampling(iSampling)

    @classmethod
    def copy_property_data(
        cls,
        inProp: IProperty,
        outProp: OProperty,
        name: list[str],
        objDepth: int,
        propDepth: int,
        *args,
        **kwargs,
    ) -> None:
        """Copy the data from an input property to an output property

        Override this method if you need to change the data that gets stored
        on a specific property

        Arguments:
            inProp (iProperty): The input property to copy data from
            outProp (oProperty): The output property to copy data to
            name (list): The full path-name of the property being copied
            objDepth (int): The depth in the *object* hierarchy that the parent
                object of this property is
            propDepth (int): The depth of the *property* hierarchy that this
                property is
        """
        if not inProp.isCompound():
            cls.copy_time_sampling(inProp, outProp, *args, **kwargs)
            for s in inProp.samples:
                outProp.setValue(s)

    @classmethod
    def copy_object_properties(
        cls,
        inObj: IObject,
        outObj: OObject,
        objDepth: int,
        debug: bool = False,
        *args,
        **kwargs,
    ) -> None:
        """Copy an input object and all of its properties to an output object

        Override this method if you need to change the structure of the properties on an object

        Arguments:
            inObj (iObject): The input object whose properties to copy from
            outObj (oObject): The output object to recieve the copied properties
            objDepth (int): The depth in the hierarchy these objects are
            debug (bool): Whether to print debug messages
            args/kwargs : Additional arguments that will get passed down the stack
                This saves you from having to override all methods to pass a single
                argument to the bottom of the call stack
        """

        iProps = inObj.getProperties()
        oProps = outObj.getProperties()
        for ip, op, propDepth, name in cls.make_prop_walk(
            iProps, oProps, *args, debug=debug, **kwargs
        ):
            cls.copy_property_data(ip, op, name, objDepth, propDepth, *args, **kwargs)

    @classmethod
    def copy_hierarchy(
        cls, inPar: IObject, outPar: OObject, debug: bool = False, *args, **kwargs
    ) -> None:
        """Start off the copying of an object hierarchy

        Arguments:
            inPar (iObject): The top-level input object to copy the hierarchy from
            outPar (oObject): The top-level output object to copy the hierarchy to
            debug (bool): Whether to print debug messages
            args/kwargs : Additional arguments that will get passed down the stack
                This saves you from having to override all methods to pass a single
                argument to the bottom of the call stack
        """
        for iChild, oChild, depth in cls.make_obj_walk(
            inPar, outPar, *args, debug=debug, **kwargs
        ):
            cls.copy_object_properties(
                iChild, oChild, depth, *args, debug=debug, **kwargs
            )

    @classmethod
    def copy_archive_time_samplings(
        cls, iArch: IArchive, oArch: OArchive, debug: bool = False, *args, **kwargs
    ) -> None:
        """Copy the time samplings from the iArch to the oArch

        Arguments:
            iArch (IArchive): The input archive object
            oArch (OArchive): The output archive object
            debug (bool): Whether to print debug messages
            args/kwargs : Additional arguments that will get passed down the stack
                This saves you from having to override all methods to pass a single
                argument to the bottom of the call stack
        """
        for idx in range(iArch.getNumTimeSamplings()):
            ts = iArch.getTimeSampling(idx)
            oArch.addTimeSampling(ts)

    @classmethod
    def copy_alembic(
        cls, inPath: str, outPath: str, debug: bool = False, *args, **kwargs
    ):
        """Start off the copying of an alembic archive

        Override this method if you need to get extra data about the
        archives before starting the copy process

        Arguments:
            inPath (str): The path to the input archive to copy
            outPath (str): The path where to create a the copied archive
            debug (bool): Whether to print debug messages
            args/kwargs : Additional arguments that will get passed down the stack
                This saves you from having to override all methods to pass a single
                argument to the bottom of the call stack
        """
        iArch = getIArchive(inPath)
        oArch = OArchive(str(outPath))
        cls.copy_archive_time_samplings(iArch, oArch, *args, debug=debug, **kwargs)

        iTop = iArch.getTop()
        oTop = oArch.getTop()
        cls.copy_hierarchy(iTop, oTop, *args, debug=debug, **kwargs)
