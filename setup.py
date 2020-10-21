import os

from setuptools import setup, find_packages

name = 'simplexui'
dirname = os.path.dirname(os.path.abspath(__file__))

# Get the long description from the README file.
with open(os.path.join(dirname, 'README.md')) as fle:
	long_description = fle.read()

setup(
	name='{}'.format(name),
	version='3.1.0',
	description=r'A cross-dcc interface for the simplex solver',
	long_description=long_description,
	url='https://github.com/blurstudio/{}'.format(name),
	download_url='https://github.com/blurstudio/{}/archive/master.tar.gz'.format(name),

	license='GNU LGPLv3',
	classifiers=[
			'Development Status :: 4 - Beta',
			'Intended Audience :: Developers',
			'Intended Audience :: End Users/Desktop',
			'Programming Language :: Python',
			'Programming Language :: Python :: 2',
			'Programming Language :: Python :: 2.7',
			'Programming Language :: Python :: Implementation :: CPython',
			'Operating System :: OS Independent',
			'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
	],
	keywords='',
	packages=find_packages(exclude=['tests']),
	include_package_data=True,
	author='Blur Studio',
	install_requires=[],
	author_email='pipeline@blur.com',
	entry_points={
		'blurdev.tools.paths': [
			'simplexui = simplexui:tool_paths',
		],
	},
)
