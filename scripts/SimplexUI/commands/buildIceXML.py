'''
Copyright 2016, Blur Studio

This file is part of Simplex.

Simplex is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Simplex is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Simplex.  If not, see <http://www.gnu.org/licenses/>.
'''

BASEXML = """<?xml version="1.0" encoding="UTF-8"?>
<xsi_file type="CompoundNode" name="ShapeCompound" formatversion="1.4" compoundversion="1.0">
\t<definition>
\t\t<nodes>
{0}
\t\t</nodes>
\t\t<exposed_ports>
\t\t\t<port index="0" portname="result" username="Result" basename="Result" portlabel="Result" exposetype="single"></port>
\t\t\t<port index="1" portname="in" username="In" basename="In" portlable="In" exposetype="single"></port>
\t\t</exposed_ports>
\t\t<connections>
{1}
\t\t</connections>
\t\t<layout>
\t\t\t<item type="input" name="In"></item>
\t\t\t<item type="output" name="Result"> </item>
\t\t</layout>
\t</definition>
</xsi_file>"""

SLIDERBASEXML = """<?xml version="1.0" encoding="UTF-8"?>
<xsi_file type="CompoundNode" name="SliderArray" formatversion="1.4" compoundversion="1.0">
\t<definition>
\t\t<nodes>
{0}
\t\t</nodes>
\t\t<exposed_ports>
\t\t\t<port index="0" portname="array" username="Array" basename="Array" portlabel="Array" exposetype="single"></port>
\t\t</exposed_ports>
\t\t<connections>
{1}
\t\t</connections>
\t\t<layout>
\t\t\t<item type="output" name="Array"> </item>
\t\t</layout>
\t</definition>
</xsi_file>"""

GETDATANODE = """
\t\t\t<node type="GetDataNode" index="{0}">
\t\t\t\t<param name="reference" type="31" value="{1}"></param>
\t\t\t\t<param_ext name="reference" type="31" value="{1}"></param_ext>
\t\t\t\t<portdef name="source" type="2048" structure="1" group="1" instance="0" port="0"></portdef>
\t\t\t\t<portdef name="inname" type="8192" structure="1" group="3" instance="0" port="0"></portdef>
\t\t\t</node>
"""

MULNODE = """
\t\t\t<node type="MultiplyByScalarNode" index="{0}">
\t\t\t\t<portdef name="value" type="16" structure="1" group="0" instance="0" port="0"></portdef>
\t\t\t\t<portdef name="factor" type="4" structure="1" group="0" instance="0" port="1"></portdef>
\t\t\t</node>
"""

BUILDARRAYNODE = """
\t\t\t<node type="BuildArrayNode" index="0">
{0}
\t\t\t</node>
"""

ADDNODE = """
\t\t\t<node type="AddNode" index="0">
{0}
\t\t\t</node>
"""

SELECTINARRAYNODE = """
\t\t\t<node type="SelectInArrayNode" index="{0}">
\t\t\t\t<param name="index" type="3" value="{1}"></param>
\t\t\t\t<param name="array" type="4" value="0.00000"></param>
\t\t\t\t<portdef name="index" type="2" structure="1" group="0" instance="0" port="0"></portdef>
\t\t\t\t<portdef name="array" type="4" structure="2" group="0" instance="0" port="0"></portdef>
\t\t\t</node>
"""

PASSTHROUGHNODE = """
\t\t\t<node type="PassThroughNode" index="{0}">
\t\t\t\t<param name="in" type="4" value="0.0000"></param>
\t\t\t\t<portdef name="in" type="4" structure="2" group="0" instance="0" port="0"></portdef>
\t\t\t</node>
"""

ADDPORT = '\t\t\t\t<portdef name="value{0}" type="16" structure="1" group="0" instance="{0}" port="0"></portdef>'
SCALARPORT = '\t\t\t\t<portdef name="value{0}" type="4" structure="1" group="0" instance="{0}" port="0"></portdef>'
CONNECTION = '\t\t\t<cnx from_node="{0}" from_port="{1}" to_node="{2}" to_port="{3}"> </cnx>'
OUTPROPERTY = "self.{0}_outProperty.{1}"
POSPROPERTY = "self.cls.{0}.{1}.positions"
INPROPERTY = "self.{0}_inProperty.{1}"

def buildIceXML(shapeList, systemName, clusterName):
	index = 1
	addIdx = 1

	addPorts = []
	nodes = []
	connections = []

	passNode = PASSTHROUGHNODE.format(index)
	nodes.append(passNode)

	index += 1

	selfPos = GETDATANODE.format(index, "Self.PointPosition")
	selfCnx = CONNECTION.format(index, 'value', 0, 'value'+str(addIdx))
	addPort = ADDPORT.format(addIdx, addIdx-1)

	nodes.append(selfPos)
	connections.append(selfCnx)
	addPorts.append(addPort)

	addIdx += 1
	index += 1

	for i,shape in enumerate(shapeList):
		sliIdx = index
		posIdx = index+1
		mulIdx = index+2

		posPropName = POSPROPERTY.format(clusterName, shape)

		sliNode = SELECTINARRAYNODE.format(sliIdx,i)
		posNode = GETDATANODE.format(posIdx, posPropName)
		mulNode = MULNODE.format(mulIdx)

		nodes.append(sliNode)
		nodes.append(posNode)
		nodes.append(mulNode)

		sliCnx = CONNECTION.format(sliIdx, 'value', mulIdx, 'factor')
		posCnx = CONNECTION.format(posIdx, 'value', mulIdx, 'value')
		addCnx = CONNECTION.format(mulIdx, 'result', 0, 'value'+str(addIdx))
		passCnx = CONNECTION.format(1, 'out', sliIdx, 'array')

		connections.append(sliCnx)
		connections.append(posCnx)
		connections.append(addCnx)
		connections.append(passCnx)

		addPort = ADDPORT.format(addIdx, addIdx-1)
		addPorts.append(addPort)

		index += 3 
		addIdx += 1

	allPorts = '\n'.join(addPorts)
	addNode = ADDNODE.format(allPorts)
	allNodes = '\n'.join(nodes)
	allNodes = addNode + '\n' + allNodes
	allConnections = '\n'.join(connections)
	output = BASEXML.format(allNodes, allConnections)

	return output

def buildSliderIceXML(sliderList, systemName):
	index = 1
	addIdx = 1

	sliderPorts = []
	nodes = []
	connections = []

	for slider in sliderList:
		inIdx = index

		inPropName = INPROPERTY.format(systemName, slider)

		inNode = GETDATANODE.format(inIdx, inPropName)

		nodes.append(inNode)

		sliderCnx = CONNECTION.format(inIdx, 'value', 0, 'value'+str(addIdx))
		connections.append(sliderCnx)

		sliderPort = SCALARPORT.format(addIdx, addIdx-1)
		sliderPorts.append(sliderPort)

		index += 1 
		addIdx += 1

	allPorts = '\n'.join(sliderPorts)
	arrayNode = BUILDARRAYNODE.format(allPorts)
	allNodes = '\n'.join(nodes)
	allNodes = arrayNode + '\n' + allNodes
	allConnections = '\n'.join(connections)
	output = SLIDERBASEXML.format(allNodes, allConnections)

	return output




