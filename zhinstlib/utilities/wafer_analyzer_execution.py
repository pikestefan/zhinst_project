from pathlib import Path
from PyQt5.QtWidgets import QApplication
from zhinstlib.gui.wafer_analyzer import WaferAnalyzer
import sys

filepath = Path(__file__).resolve().parents[1]
qss = filepath / "artwork" / "wafer_analyzer_style.qss"
app = QApplication(sys.argv)
with open(qss, "r") as fh:
    app.setStyleSheet(fh.read())
window = WaferAnalyzer()
sys.exit(app.exec_())
