from PyQt5.QtWidgets import QTextEdit,QSizePolicy, QWidget
from PyQt5.QtCore import pyqtSignal, QEvent

class InteractingLineEdit(QTextEdit):

    signal_widget_clicked = pyqtSignal(str)
    def __init__(self, id, fixed_size = 80, *args, **kwargs):
        super(InteractingLineEdit, self).__init__(*args, **kwargs)
        self.id = id
        self.setEnabled(False)
        self.setSizePolicy( QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) )
        self.fixed_size = fixed_size
        self.setFixedSize(self.fixed_size, self.fixed_size)
        self._stylesheet_modes = {"standard": {"no hover": "background-color:rgb(204,204,204);border: 1px solid black;",
                                              "hover": "background-color:rgb(204,204,204);border: 3px solid red;",
                                              "clicked" : "background-color:rgb(255,183,67);border: 3px solid rgb(0,148,49);"},
                                 "data loaded": {"no hover": "background-color:rgb(155,225,199);border: 1px solid rgb(0,0,0);",
                                                 "hover": "background-color:rgb(155,225,199);border: 3px solid rgb(0,118,19);",
                                                 "clicked" : "background-color:rgb(158,255,245);border: 3px solid rgb(0,148,49);"},
                                 "data missing": {"no hover": "background-color:rgb(150,150,150);border: 1px solid black;",
                                                  "hover": "background-color:rgb(204,204,204);border: 3px solid red;",
                                                  "clicked" : "background-color:rgb(158,255,245);border: 3px solid rgb(0,148,49);"},
                                 }
        self._active_stylesheet = self._stylesheet_modes["standard"]
        self.setStyleSheet(self._active_stylesheet["no hover"])
        self.isclicked = False
        self._interaction_enabled = True
        self.installEventFilter(self)

    def eventFilter(self, source, event):
        if (source is self) and self._interaction_enabled:
            if event.type() == QEvent.Enter and not self.isclicked:
                self.setStyleSheet(self._active_stylesheet["hover"])
            elif event.type() == QEvent.Leave and not self.isclicked:
                self.setStyleSheet(self._active_stylesheet["no hover"])
            elif event.type() == QEvent.MouseButtonPress:
                if not self.isclicked:
                    self.isclicked = True
                    self.setStyleSheet(self._active_stylesheet["clicked"])
                else:
                    self.isclicked = False
                    self.setStyleSheet(self._active_stylesheet["hover"])
                self.signal_widget_clicked.emit(self.id)
        return QWidget.eventFilter(self, source, event)

    def unclick(self):
        self.isclicked = False
        self.setStyleSheet(self._active_stylesheet["no hover"])
        self.signal_widget_clicked.emit(self.id)

    def interaction_enabled(self, value):
        self._interaction_enabled = value

    def set_active_stylesheet(self, style_name):
        if style_name not in self._stylesheet_modes.keys():
            print("Invalid style list")
        else:
            self._active_stylesheet = self._stylesheet_modes[style_name]
            if self.isclicked:
                self.setStyleSheet(self._active_stylesheet["clicked"])
            else:
                self.setStyleSheet(self._active_stylesheet["no hover"])