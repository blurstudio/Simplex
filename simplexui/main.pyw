import blurdev

if __name__ == "__main__":
	# Ensure that my custom Qt.py import uses PyQt5
	import os
	import json
	pref = json.loads(os.environ.get("QT_PREFERRED_BINDING_JSON", "{}"))
	pref.setdefault("SimplexUI.Qt", ["PyQt5", "PyQt4"])
	os.environ["QT_PREFERRED_BINDING_JSON"] = json.dumps(pref)

	from SimplexUI.simplexDialog import SimplexDialog
	import SimplexUI
	import blur3d
	dlg = blur3d.launch(SimplexDialog)
	try:
		# Store the last simplex launch in these module variables
		SimplexUI.SIMPLEX_UI_ROOT = dlg.parent()
		SimplexUI.SIMPLEX_UI = dlg
	except RuntimeError:
		# If dlg.parent() raises a runtime error, then the ui has already been deleted
		# This happens if we're running externally instead of internally
		pass
