_standards = """
QWidget{
	font: 8pt "MS Shell Dlg 2";
}

QLineEdit{
	border-radius: 4px;
	padding-left: 3px;
	padding-Top: 1px;
	padding-bottom: 1px;
}

QFrame{
	border: none;
}

QPushButton, QToolButton{
	border-radius: 4px;
}

QPushButton{
	padding: 5px;
	min-width: 60px;
}

QToolButton{
	padding-left: 5px;
	padding-top: 1px;
	padding-right: 5px;
	padding-bottom: 1px;
}

QSplitter::handle{
	height: 3px;
}

QScrollBar:handle:horizontal, QScrollBar:handle:vertical{
	border-width: 0;
	border-radius: 5;
}

QGroupBox{
	border-radius: 5px;
	margin-top: 11px;
	padding: 4px 0px;
	font: 7pt;
}

QGroupBox::title {
	subcontrol-origin: margin;
	subcontrol-position: top left;
	left: 10px;
}

"""


Default = _standards + """

QPushButton, QToolButton{
	background-color: rgb(100, 100, 100);
}

QPushButton:Hover, QToolButton:Hover{
	background-color: rgb(120, 120, 120);
}

QPushButton:Pressed, QToolButton:Pressed{
	background-color: rgb(50, 50, 50);
}

QSplitter::handle{
	background-color: none;
}

QGroupBox{
	background-color: rgb(80, 80, 80);
}

"""


Solarized = _standards + """
QWidget{
	color: rgb(117, 201, 255);
	background-color: rgb(27, 42, 66);
	alternate-background-color: rgb(31, 49, 77);
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox{
	background-color: rgb(46, 75, 117);
}

QPushButton, QToolButton{
	background-color: rgb(46, 75, 117);
}

QPushButton:Hover, QToolButton:Hover, QMenu::item:selected{
	background-color: rgb(57, 93, 145);
}

QPushButton:Pressed, QToolButton:Pressed{
	background-color: rgb(27, 42, 66);
}

QGroupBox, QCheckBox, QRadioButton{
	color: rgb(85, 180, 239);
	background-color: rgb(31, 49, 77);
}

QLabel{
	background-color: rgba(0, 0, 0, 0);
}

QHeaderView:section{
	font: 7pt;
	border: 1px solid rgb(27, 42, 66);
	background-color: rgb(31, 49, 77);
	padding-left: 6px;
}

QSplitter::handle{
	background-color: rgb(27, 42, 66);
}

QScrollBar:handle:horizontal, QScrollBar:handle:vertical{
	background-color: rgb(46, 75, 117);
}

QScrollBar::add-page, QScrollBar::sub-page {
	background: rgb(27, 42, 66);
}

"""

