.PHONY: \
	help \
	generate_maya \
	generate_python \
	generate_xsi \
	build_maya \
	build_python \
	build_xsi \
	install_maya \
	install_python \
	install_xsi \
	clean \


CMAKE = cmake

MAYA_VERSION = 2019
MAYA_BUILD_DIR = mayabuild

PYTHON_VERSION = 2.7
PYTHON_BUILD_DIR = pybuild

XSI_VERSION = 2015
XSI_BUILD_DIR = xsibuild

#-----------------------------------------------------------------------------#
# cmake generate targets
#-----------------------------------------------------------------------------#

generate_maya::
	rm -rf $(MAYA_BUILD_DIR)
	mkdir -p $(MAYA_BUILD_DIR)
	$(CMAKE) -DMAYA_VERSION=$(MAYA_VERSION) -B$(MAYA_BUILD_DIR)

generate_python::
	rm -rf $(PYTHON_BUILD_DIR)
	mkdir -p $(PYTHON_BUILD_DIR)
	$(CMAKE) -DPY_VERSION=$(PYTHON_VERSION) -DTARGET_DCC=Python -B$(PYTHON_BUILD_DIR)

generate_xsi::
	rm -rf $(XSI_BUILD_DIR)
	mkdir -p $(XSI_BUILD_DIR)
	$(CMAKE) -DXSI_VERSION=$(XSI_VERSION) -DTARGET_DCC=XSI -B$(XSI_BUILD_DIR)

#-----------------------------------------------------------------------------#
# cmake build targets
#-----------------------------------------------------------------------------#

build_maya::
	cmake --build $(MAYA_BUILD_DIR) --config Release

build_python::
	cmake --build $(PYTHON_BUILD_DIR) --config Release

build_xsi::
	cmake --build $(XSI_BUILD_DIR) --config Release

#-----------------------------------------------------------------------------#
# cmake build targets
#-----------------------------------------------------------------------------#

install_maya::
	cmake --install $(MAYA_BUILD_DIR) --config Release

install_python::
	cmake --install $(PYTHON_BUILD_DIR) --config Release

install_xsi::
	cmake --install $(XSI_BUILD_DIR) --config Release


clean::
	rm -rf $(MAYA_BUILD_DIR)
	rm -rf $(PYTHON_BUILD_DIR)
	rm -rf $(XSI_BUILD_DIR)
