from PyQt5.QtWidgets import QTextEdit,QSizePolicy, QWidget, QMenu
from PyQt5.QtCore import pyqtSignal, QEvent
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction

class InteractingLineEdit(QTextEdit):

    signal_widget_clicked = pyqtSignal(str)
    def __init__(self, id, fixed_size = 80, *args, **kwargs):
        super(InteractingLineEdit, self).__init__(*args, **kwargs)
        self.id = id
        self.setEnabled(False)
        self.setSizePolicy( QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) )
        self.fixed_size = fixed_size
        self.setFixedSize(self.fixed_size, self.fixed_size)

        self._stylesheet_modes = {"standard": {"no hover": "background-color:rgb(204,204,204);border: 1px solid black; font-size:10px; color:k",
                                              "hover": "background-color:rgb(204,204,204);border: 3px solid red; font-size:10px; color:k",
                                              "clicked" : "background-color:rgb(255,183,67);border: 3px solid rgb(0,148,49); font-size:10px; color:k"},
                                 "data loaded": {"no hover": "background-color:rgb(155,225,199);border: 1px solid rgb(0,0,0); font-size:10px; color:k",
                                                 "hover": "background-color:rgb(155,225,199);border: 3px solid rgb(0,118,19); font-size:10px; color:k",
                                                 "clicked" : "background-color:rgb(158,255,245);border: 3px solid rgb(0,148,49); font-size:10px; color:k"},
                                 "data missing": {"no hover": "background-color:rgb(150,150,150);border: 1px solid black; font-size:10px; color:k"},
                                 "damaged": {"no hover": "background-color:rgb(255,189,193);border: 1px solid black; font-size:10px; color:k",
                                             "hover": "background-color:rgb(255,189,193);border: 3px solid red; font-size:10px; color:k",
                                             "clicked": "background-color:rgb(255,86,98);border: 3px solid rgb(0,148,49); font-size:10px; color:k"},
                                 }
        self._active_stylesheet = self._stylesheet_modes["standard"]
        self.setStyleSheet(self._active_stylesheet["no hover"])
        self.isclicked = False
        self._data_uploaded = False
        self._interaction_enabled = True
        self.installEventFilter(self)

    def eventFilter(self, source, event):
        if (source is self) and self._interaction_enabled:
            if event.type() == QEvent.Enter and not self.isclicked:
                self.setStyleSheet(self._active_stylesheet["hover"])
            elif event.type() == QEvent.Leave and not self.isclicked:
                self.setStyleSheet(self._active_stylesheet["no hover"])
            elif event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    if not self.isclicked:
                        self.isclicked = True
                        self.setStyleSheet(self._active_stylesheet["clicked"])
                    else:
                        self.isclicked = False
                        self.setStyleSheet(self._active_stylesheet["hover"])
                    self.signal_widget_clicked.emit(self.id)
                elif event.button() == Qt.RightButton:
                    menu = QMenu()
                    damaged = menu.addAction('Mark as damaged')
                    usable = menu.addAction('Mark as usable')
                    if menu.exec_(event.globalPos()) == damaged:
                        self.set_active_stylesheet("damaged")
                    else:
                        if self._data_uploaded:
                            self.set_active_stylesheet("data loaded")
                        else:
                            self.set_active_stylesheet("standard")


        return QWidget.eventFilter(self, source, event)

    def set_interacting(self, value):
        self._interaction_enabled = value

    def unclick(self):
        self.isclicked = False
        self.setStyleSheet(self._active_stylesheet["no hover"])
        self.signal_widget_clicked.emit(self.id)

    def set_active_stylesheet(self, style_name):
        if style_name not in self._stylesheet_modes.keys():
            print("Invalid style list")
        else:
            self._active_stylesheet = self._stylesheet_modes[style_name]
            if self.isclicked:
                self.setStyleSheet(self._active_stylesheet["clicked"])
            else:
                self.setStyleSheet(self._active_stylesheet["no hover"])

    def isActivated(self):
        return self._interaction_enabled

    def setActivated(self, active):
        self._interaction_enabled = active
        if active is False:
            stylesheet = self._stylesheet_modes["data missing"]
        else:
            if self._data_uploaded:
                stylesheet = self._stylesheet_modes["data loaded"]
            else:
                stylesheet = self._stylesheet_modes["standard"]

        self._active_stylesheet = stylesheet
        self.setStyleSheet(self._active_stylesheet["no hover"])

    def setDataUploaded(self, value):
        if not self._interaction_enabled:
            return

        self._data_uploaded = value
        if value is True:
            self._active_stylesheet = self._stylesheet_modes["data loaded"]
        else:
            self._active_stylesheet = self._stylesheet_modes["standard"]

        if self.isclicked:
            self.setStyleSheet(self._active_stylesheet["clicked"])
        else:
            self.setStyleSheet(self._active_stylesheet["no hover"])

    def hasData(self):
        return self._data_uploaded