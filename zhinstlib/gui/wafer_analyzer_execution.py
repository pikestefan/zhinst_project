from pathlib import Path
from PyQt5.QtWidgets import QApplication
from zhinstlib.gui.wafer_analyzer import WaferAnalyzer
import sys

filepath = Path(__file__).parents[1]
qss = filepath / "ui_files" / "wafer_analyzer_style.qss"
app = QApplication(sys.argv)
with open(qss, "r") as fh:
    app.setStyleSheet(fh.read())
window = WaferAnalyzer()
sys.exit(app.exec_())
# sys.exit()