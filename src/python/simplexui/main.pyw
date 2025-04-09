import blurdev

if __name__ == "__main__":
	# Ensure that my custom Qt.py import uses PyQt5
	import os
	import json
	pref = json.loads(os.environ.get("QT_PREFERRED_BINDING_JSON", "{}"))
	pref.setdefault("simplexui.Qt", ["PyQt5", "PyQt4"])
	os.environ["QT_PREFERRED_BINDING_JSON"] = json.dumps(pref)
	os.environ["SIMPLEX_AT_BLUR"] = "true"

	from simplexui.simplexDialog import SimplexDialog
	import simplexui
	dlg = blurdev.launch(SimplexDialog)
	try:
		# Store the last simplex launch in these module variables
		simplexui.SIMPLEX_UI_ROOT = dlg.parent()
		simplexui.SIMPLEX_UI = dlg
	except RuntimeError:
		# If dlg.parent() raises a runtime error, then the ui has already been deleted
		# This happens if we're running externally instead of internally
		pass
