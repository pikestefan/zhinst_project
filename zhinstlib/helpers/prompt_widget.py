from PyQt5.QtWidgets import (
    QDialog,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QApplication,
)
import sys
from PyQt5.QtCore import Qt


def prompt_at_overwrite(custom_error_msg=""):
    app = QApplication(sys.argv)
    window = PromptWidget(custom_error_msg)
    window.setAttribute(Qt.WA_DeleteOnClose)
    if window.exec_() == QDialog.Accepted:
        value = window.okbutton_pressed
    return value


class PromptWidget(QDialog):
    def __init__(self, custom_error_msg="", *args, **kwargs):
        super(PromptWidget, self).__init__(*args, **kwargs)
        if custom_error_msg == "":
            custom_error_msg = "Proceeding will erase an existing file. Continue?"

        layout = QVBoxLayout()

        text = QLabel()
        text.setText(custom_error_msg)

        self.okbutton = QPushButton("OK")
        self.nobutton = QPushButton("Cancel")

        self.okbutton.clicked.connect(self.close)
        self.nobutton.clicked.connect(self.close)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.okbutton)
        hlayout.addWidget(self.nobutton)

        layout.addWidget(text)
        layout.addLayout(hlayout)

        self.setLayout(layout)

        self.okbutton_pressed = False

    def closeEvent(self, event):
        if self.sender() == self.okbutton:
            self.okbutton_pressed = True
        self.accept()


if __name__ == "__main__":
    val = prompt_at_overwrite()
    print(val)
