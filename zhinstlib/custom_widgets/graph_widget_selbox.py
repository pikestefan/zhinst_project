import sys
from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
import pyqtgraph as pg
from pyqtgraph import PlotWidget, plot

# *********************************************************************************************
# *********************************************************************************************

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("My MainWindow")
        self.qPlotWidget = pg.PlotWidget(self)
        self.qPlotWidget.setLabel("bottom", "X-Axis")
        self.qPlotWidget.setLabel("left", "Y-Axis")
        self.qPlotWidget.scene().sigMouseClicked.connect(self.mouseClickedEvent)

        data1 = np.zeros((2, 2), float) # create the array to hold the data
        data1[0] = np.array((1.0, 10.0))
        data1[1] = np.array((2.0, 20.0))

        pen1 = pg.mkPen(color=(255,0,0), width=1) # red
        self.qPlotWidget.plot(data1, pen=pen1, name="data1")

    def mouseClickedEvent(self, event):
        print("mouseClickedEvent")
        pos = event.scenePos()
        if (self.qPlotWidget.sceneBoundingRect().contains(pos)):
            mousePoint = self.qPlotWidget.plotItem.vb.mapSceneToView(pos)
            print("mousePoint=", mousePoint)

            # draw and fill a 2-pixel by 2-pixel red rectangle where
            # the mouse was clicked at [mousePoint.x(), mousePoint.y()]
            # ??? add code here

    def resizeEvent(self, event):
        size = self.geometry()
        self.qPlotWidget.setGeometry(10, 10, size.width()-20, size.height()-20)

class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(30,30,600,400)
        self.begin = QtCore.QPoint()
        self.end = QtCore.QPoint()
        self.show()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        br = QtGui.QBrush(QtGui.QColor(100, 10, 10, 40))
        qp.setBrush(br)
        qp.drawRect(QtCore.QRect(self.begin, self.end))

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.begin = event.pos()
        self.end = event.pos()
        self.update()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    w = MainWindow()
    screen = QtWidgets.QDesktopWidget().screenGeometry()
    w.setGeometry(100, 100, screen.width()-200, screen.height()-200) # x, y, Width, Height
    w.show()

    sys.exit(app.exec_())