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


from .alembic_walker import AlembicWalker

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alembic.Abc import IProperty, OProperty


class ReplaceSmpxAttr(AlembicWalker):
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

        if name[-1] == 'simplex' and 'newjs' in kwargs:
            if not inProp.isCompound():
                AlembicWalker.copy_time_sampling(inProp, outProp, *args, **kwargs)
                for _ in inProp.samples:
                    outProp.setValue(kwargs['newjs'])
        else:
            AlembicWalker.copy_property_data(
                inProp, outProp, name, objDepth, propDepth, *args, **kwargs
            )


def replaceDefinitionJson(inSmpxPath: str, outSmpxPath: str, newJsonString: str):
    """Given a simplex file, make a copy of that file with the new json definition string
    This is good for doing manual renames and edits of the json

    Args:
        inSmpxPath (str): The filepath to the existing simplex
        outSmpxPath (str): The filepath save the new simplex
        newJsonString (str): The json string that will replace the old one
    """
    ReplaceSmpxAttr.copy_alembic(inSmpxPath, outSmpxPath, newjs=newJsonString)
