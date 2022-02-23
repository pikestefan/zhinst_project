from PyQt5.QtWidgets import * #QWidget, QGridLayout, QLabel, QSpacerItem
from PyQt5.QtWidgets import * #QSizePolicy
from PyQt5.QtCore import * #pyqtSignal, Qt
from zhinstlib.custom_widgets.mouse_interacting_lineedit import InteractingLineEdit

class InteractiveWafer(QWidget):

    signal_id_changed = pyqtSignal(str)

    def __init__(self, rows=1, cols=1, fixed_size=100, *args, **kwargs):
        super(InteractiveWafer, self).__init__()
        self.rows = rows
        self.cols = cols
        self.fixed_size = fixed_size #The size of the square side
        self.chip_collection = dict()
        self.do_grid()
        self.current_active = None
        self.setAutoFillBackground(False)

    def do_grid(self):
        layout = QGridLayout()
        self.setLayout(layout)

        for ii in range(1, self.rows + 1):
            for jj in range(1, self.cols + 1):
                if jj == 1:
                    widgy = QLabel(str(ii))
                    widgy.setStyleSheet("font-weight: bold;")
                    layout.addWidget(widgy, ii + 1, jj, Qt.AlignVCenter)

                    # This widget is used for centering purposes
                    widgy = QLabel(str(ii))
                    widgy.setStyleSheet("font-weight: bold; color:rgba(0,0,0,0)")
                    layout.addWidget(widgy, ii + 1, jj + self.cols + 1, Qt.AlignVCenter)
                if ii == 1:
                    widgy = QLabel(chr(ord('A') + jj - 1))
                    widgy.setStyleSheet("font-weight: bold;")
                    layout.addWidget(widgy, ii, jj + 1, Qt.AlignHCenter)

                    # This widget is used for centering purposes
                    widgy = QLabel(chr(ord('A') + jj - 1))
                    widgy.setStyleSheet("font-weight: bold; color:rgba(0,0,0,0)")
                    layout.addWidget(widgy, ii + self.rows + 1, jj + 1, Qt.AlignHCenter)

        for ii in range(2, self.rows + 2):
            for jj in range(2, self.cols + 2):
                if (ii != 2 and ii != self.rows + 1) or (jj != 2 and jj != self.cols + 1):
                    temp_id = chr(ord('A') + jj - 2) + str(ii-1)
                    widgy = InteractingLineEdit(temp_id, self.fixed_size)
                    self.chip_collection[temp_id] = widgy
                    widgy.signal_widget_clicked.connect(self.update_square)
                    layout.addWidget(widgy, ii, jj)

        #Add four spacers on the four square corners to center the chips
        hor_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        ver_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        layout.addItem(hor_spacer, 1, 0)
        layout.addItem(hor_spacer, 1, self.cols + 3)
        layout.addItem(ver_spacer, 0, 1)
        layout.addItem(ver_spacer, self.rows + 3, 1)
        layout.setHorizontalSpacing(3)
        layout.setVerticalSpacing(3)

    def update_square(self, id):
        if not self.current_active:
            self.current_active = id
        elif self.current_active != id:
            self.chip_collection[self.current_active].unclick()
            self.current_active = id
        elif self.current_active == id:
            self.current_active = ''
        self.signal_id_changed.emit(self.current_active)

    def set_inactive_chips(self, chipID_list):
        for chipID in chipID_list:
            self.chip_collection[chipID].setActivated(False)

class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            # See below for the nested-list data structure.
            # .row() indexes into the outer list,
            # .column() indexes into the sub-list
            return self._data[index.row()][index.column()]

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._data[0])

class test(QWidget):
    def __init__(self):
        super(test, self).__init__()
        layout = QHBoxLayout(self)
        self.table = QTableWidget()

        data = [
            [4, 9, 2, 1, 1],
            [1, 0, 0, 1, 7],
            [3, 5, 0, 4, 7],
            [3, 3, 2, 7, 2],
            [7, 8, 9, 1, 0],
        ]

        self.table.setRowCount(5)
        self.table.setColumnCount(5)

        #self.model = TableModel(data)
        #self.table.setModel(self.model)
        style_list = """
                        QTableWidget {background-color:white; gridline-color:white; color:black; selection-color:black;}
                        QTableWidget::item {color:white; background:black;}
                        QTableWidget::item:hover {color:black; background:orange; border:1px solid red;}
                        QTableWidget::item:selected {color:black; background:green; border:3px solid blue;}
                     """
        self.setStyleSheet(style_list)

        for ii in range(5):
            self.table.setRowHeight(ii, 50)
        for jj in range(5):
            self.table.setColumnWidth(jj, 50)

        layout.addWidget(self.table)

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = test()
    window.show()
    sys.exit(app.exec_())
    # sys.exit()