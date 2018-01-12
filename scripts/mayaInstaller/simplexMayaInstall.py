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

# Thanks to @dgovil on github for posting a gist of this to get me started

#pylint:disable=missing-docstring,superfluous-parens
import os, shutil, zipfile, urllib2, tempfile
from maya import cmds

def downloadSimplex(tempDir, releaseVersion=None, commitHash=None):
	print("Downloading Simplex")
	dest = os.path.join(tempDir, 'simplex.zip')

	dlPath = None
	if releaseVersion is not None:
		dlPath = 'https://github.com/blurstudio/Simplex/releases/download/{0}/Simplex.zip'.format(releaseVersion)
	elif commitHash is not None:
		dlPath = 'https://github.com/blurstudio/Simplex/archive/{0}.zip'.format(commitHash)
	else:
		dlPath = 'https://github.com/blurstudio/Simplex/archive/master.zip'

	with open(dest, 'wb') as f:
		f.write(urllib2.urlopen(dlPath).read())

	print("Download Complete! Downloaded to {0}".format(dest))
	return dest

def extract(filepath, userScriptDir):
	print("Extracting file")

	target = os.path.join(userScriptDir, 'Simplex')
	if os.path.exists(target):
		print("Simplex is already extracted here: %s" % target)
		return target

	with zipfile.ZipFile(filepath, 'r') as z:
		z.extractall(target)

	if not os.path.exists(target):
		msg = "Could not find the Simplex directory at {0}".format(target)
		cmds.confirmDialog(title='Error', message=msg, button=['OK'], defaultButton='OK')
		raise IOError("Incorrect extraction path")

	print("Extracted Simplex to %s" % target)
	return target

def installScriptDir(source, target):
	print("Copying Script")
	if os.path.isdir(target):
		shutil.rmtree(target)
	shutil.copytree(source, target)

def installPlugin(source, target):
	print("Copying Plugin")
	if cmds.pluginInfo('simplex_maya.mll', loaded=True, query=True):
		cmds.unloadPlugin('simplex_maya.mll')
	if not os.path.isdir(os.path.dirname(target)):
		os.makedirs(os.path.dirname(target))
	shutil.move(source, target)
	cmds.loadPlugin(target)

def installCheckout(commitHash=None):
	userScriptDir = cmds.internalVar(userScriptDir=True)

	tempDir = tempfile.mkdtemp()
	if not os.path.isdir(tempDir):
		os.makedirs(tempDir)

	download = downloadSimplex(tempDir, commitHash)
	extractFolder = extract(download, tempDir)

	scriptSrc = os.path.join(extractFolder, 'Simplex-master', 'scripts', 'SimplexUI')
	scriptTar = os.path.join(userScriptDir, 'SimplexUI')

	installScriptDir(scriptSrc, scriptTar)
	shutil.rmtree(tempDir)
	print "Simplex Installed"

def installRelease(releaseVersion='1.0.3'):
	userScriptDir = os.path.normpath(cmds.internalVar(userScriptDir=True))
	# Do it this way because cmds.about(version=1) returns "2016 Extension 2"
	mayaVersion = os.path.basename(os.path.dirname(userScriptDir))

	if cmds.pluginInfo('simplex-maya', loaded=True, query=True):
		if not cmds.pluginInfo('simplex-maya', unloadOk=True, query=True):
			msg = 'Simplex is currently in use.\nPlease open a fresh file to free it'
			cmds.confirmDialog(title='Plugin In Use', message=msg, button=['OK'], defaultButton='OK')
			raise IOError('Plugin in use')

	userPluginDir = os.path.join(os.path.dirname(userScriptDir), 'plug-ins')

	tempDir = tempfile.mkdtemp()
	if not os.path.isdir(tempDir):
		os.makedirs(tempDir)

	download = downloadSimplex(tempDir, releaseVersion=releaseVersion)
	extractFolder = extract(download, tempDir)

	scriptSrc = os.path.join(extractFolder, 'Simplex', 'SimplexUI')

	verName = 'maya{0}'.format(mayaVersion)
	pluginSrc = os.path.join(extractFolder, 'Simplex', verName, 'plug-ins', 'simplex_maya.mll')
	pluginSrcDir = os.path.dirname(pluginSrc)
	if not os.path.isdir(pluginSrcDir):
		msg = 'Simplex is not compiled for this version of maya: {0}'.format(mayaVersion)
		cmds.confirmDialog(title='Not Compiled', message=msg, button=['OK'], defaultButton='OK')
		raise IOError('File does not exist')

	scriptTar = os.path.join(userScriptDir, 'SimplexUI')
	pluginTar = os.path.join(userPluginDir, 'simplex_maya.mll')

	installScriptDir(scriptSrc, scriptTar)
	installPlugin(pluginSrc, pluginTar)
	shutil.rmtree(tempDir)
	print "Simplex Installed"

if __name__ == "__main__":
	installRelease()
	installCheckout()

