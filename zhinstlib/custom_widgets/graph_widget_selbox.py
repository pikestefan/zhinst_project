import sys

import pyqtgraph
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal
import numpy as np
import pyqtgraph as pg
from pyqtgraph import PlotWidget, PlotDataItem


class SelectableAreaPlotWidget(pg.PlotWidget):
    areaSelectedSignal = pyqtSignal(float, float)

    def __init__(self, *args, **kwargs):
        kwargs['viewBox'] = ViewForBoxDrag()
        super(SelectableAreaPlotWidget, self).__init__(*args, **kwargs)
        #self.blo = pg.PlotDataItem(np.array([0,1,2]), np.square(np.array([0,1,2])))
        #self.addItem(self.blo)
        self.rect = None

        self.getViewBox().signalUpdateRect.connect(self.drawRect)
        self.getViewBox().signalClearRect.connect(self.hideRect)

    def drawRect(self, qrectf):
        if self.rect is None:
            self.getViewBox().disableAutoRange()
            self.rect = pg.QtGui.QGraphicsRectItem(qrectf)
            self.rect.setPen(pg.mkPen(None))
            self.rect.setBrush(pg.mkBrush(color=(219, 212, 0, 80)))
            self.addItem(self.rect)
        self.rect.setRect(qrectf)

    def hideRect(self, xrange):
        self.removeItem(self.rect)
        self.rect = None
        self.getViewBox().enableAutoRange()
        self.setXRange(xrange[0], xrange[1], padding=0)

class DownsamplerPlotDataItem(PlotDataItem):
    """
    A custom PlotDataItem that resamples the data, to increase the plotting speed.
    """
    def __init__(self, max_data = 1e20, *args, **kwargs):
        self.max_data = max_data

        if len(args) == 2:
            x_ax = args[0]
            y_ax = args[1]
            if len(x_ax) > self.max_data:
                args = self.resample_data(x_ax, y_ax)
        if 'x' in kwargs and 'y' in kwargs:
            x_ax = kwargs['x']
            y_ax = kwargs['y']
            if len(x_ax) > self.max_data:
                kwargs['x'], kwargs['y'] = self.resample_data(x_ax, y_ax)

        super(DownsamplerPlotDataItem, self).__init__(*args, **kwargs)

    def resample_data(self, x, y):
        new_x = np.linspace(x[0], x[-1], self.max_data)
        new_y = np.interp(new_x, x, y)
        return new_x, new_y

    def setData(self, *args, **kwargs):
        if len(args) == 2:
            x_ax = args[0]
            y_ax = args[1]
            if len(x_ax) > self.max_data:
                args = self.resample_data(x_ax, y_ax)
        if 'x' in kwargs and 'y' in kwargs:
            x_ax = kwargs['x']
            y_ax = kwargs['y']
            if len(x_ax) > self.max_data:
                kwargs['x'], kwargs['y'] = self.resample_data(x_ax, y_ax)

        super().setData(*args,**kwargs)

class ViewForBoxDrag(pg.ViewBox):
    signalUpdateRect = pyqtSignal(QtCore.QRectF)
    signalClearRect = pyqtSignal(list)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start = None
        self.viewHeight = None
        self.y0 = None

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            if ev.isStart():
                #TODO: fix this, it is cleaner to get the coordinate at the beginning of drag with the ev.buttonDown() or
                # something along those lines
                self.start = self.mapToView(ev.pos())
                _, yviewrange = self.viewRange()
                self.y0 = yviewrange[0]
                self.viewHeight = yviewrange[1] - self.y0
            else:
                keymods = QtWidgets.QApplication.keyboardModifiers()
                currpos = self.mapToView(ev.pos())

                #Negative widths and heights cause issues in the correct displaying of images
                x0 = self.start.x() if self.start.x() <= currpos.x() else currpos.x()
                width = abs(currpos.x() - self.start.x())

                #Make a plot-tall selection if you hold shift and drag
                if keymods and QtCore.Qt.ShiftModifier:
                    height = self.viewHeight
                    y0 = self.y0
                #Otherwise, just draw a square
                else:
                    height = abs(currpos.y() - self.start.y())
                    y0 = self.start.y() if self.start.y() <= currpos.y() else currpos.y()
                self.signalUpdateRect.emit(QtCore.QRectF(x0, y0, width, height))
            if ev.isFinish():
                #TODO: at the moment, the signal emits only the x range. Send also the y range, and use it
                # to rescale the plot when dragging the square selection, while do nothing if pressing shift
                xpositions = [self.start.x(), self.mapToView(ev.pos()).x()]
                xpositions.sort()
                self.signalClearRect.emit(xpositions)
        else:
            super().mouseDragEvent(ev)

    def mouseDoubleClickEvent(self, ev, axis=None):
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            self.autoRange()
        else:
            super().mouseDoubleClickEvent()

if __name__ == '__main__':

    app = QtWidgets.QApplication(sys.argv)

    w = SelectableAreaPlotWidget()
    x, y = np.linspace(0,100,100000), np.random.rand(100000)**2
    sgnu = DownsamplerPlotDataItem(max_data=50000, pen = None, symbol = 'o', symbolPen = pg.mkPen('w'), symbolBrush = 'w', symbolSize = 3)
    sgnu.setData(x, y)

    w.addItem(sgnu)
    #screen = QtWidgets.QDesktopWidget().screenGeometry()
    #w.setGeometry(100, 100, screen.width()-200, screen.height()-200) # x, y, Width, Height
    w.show()

    sys.exit(app.exec_())