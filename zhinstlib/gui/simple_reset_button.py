# -*- coding: utf-8 -*-
"""
Created on Wed Aug 11 13:21:21 2021

@author: QMPL
"""

import sys
import os
from pathlib import Path
import PyQt5.QtWidgets as qwid
import PyQt5.QtCore as qcore
from helpers.helper_funcs import get_device_props
from zhinstlib.core.zinst_device import ziVirtualDevice
import time


class ResetButton(qwid.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResetButton, self).__init__(*args, **kwargs)
        self.timer = qcore.QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.check_and_reset)

        self.zinst_dev = None
        self.connected = False

        layout = qwid.QVBoxLayout()

        self.text_edit = qwid.QLineEdit('dev5152')
        layout.addWidget(self.text_edit)

        self.connect_button = qwid.QPushButton(text='Connect to device')
        self.connect_button.clicked.connect(self.connect_to_dev)
        layout.addWidget(self.connect_button)

        hlayout = qwid.QHBoxLayout()
        self.check_box_list = []
        for ii in range(4):
            loc_cbox = qwid.QCheckBox()
            loc_cbox.setText(f'PID {ii}')
            hlayout.addWidget(loc_cbox)
            self.check_box_list.append(loc_cbox)
        layout.addLayout(hlayout)

        self.reset_button = qwid.QPushButton(text='Reset PIDs')
        self.reset_button.clicked.connect(self.reset_pids)
        layout.addWidget(self.reset_button)

        start_watch = qwid.QPushButton(text='Auto lock-reset')
        start_watch.setCheckable(True)
        start_watch.toggled.connect(self.automatic_pid_reset)
        layout.addWidget(start_watch)
        self.setLayout(layout)

        self.setObjectName('PID reset button')
        self.show()

    @qcore.pyqtSlot()
    def connect_to_dev(self):
        if not self.connected:
            device_id = self.text_edit.text()
            props = get_device_props(device_id)

            dev = ziVirtualDevice(device_id, props['serveraddress'], props['serverport'], props['apilevel'])

            if dev is not None:
                self.connected = True
                self.zinst_dev = dev
                print('Connected.')
                self.text_edit.setDisabled(True)
                self.connect_button.setDisabled(True)
        else:
            print("Already connected.")

    @qcore.pyqtSlot()
    def reset_pids(self):
        for ii, cbox in enumerate(self.check_box_list):
            if cbox.isChecked():
                self.zinst_dev.set_pid_enabled(ii, False)
                self.zinst_dev.sync()
                self.zinst_dev.set_aux_offset(ii, 0)
                self.zinst_dev.sync()
                self.zinst_dev.set_pid_enabled(ii, True)

    @qcore.pyqtSlot(bool)
    def automatic_pid_reset(self, btn_clicked):

        if btn_clicked:
            self.activate_buttons(set_active=btn_clicked)
            self.timer.start()
            print("Started listening.")
        else:
            self.timer.stop()
            self.activate_buttons(set_active=btn_clicked)
            print("Stopped listening.")

    @qcore.pyqtSlot()
    def check_and_reset(self):
        for ii, aux_chan in enumerate(self.check_box_list):
            if aux_chan.isChecked():
                offset = self.zinst_dev.get_aux_offset(ii)
                if (offset < -9) or (offset > 9):
                    self.zinst_dev.set_pid_enabled(ii, False)
                    self.zinst_dev.set_aux_offset(ii, 0)

                    self.zinst_dev.set_pid_enabled(ii, True)
                    tod = time.localtime()
                    tod_mins = f"0{tod.tm_min}" if tod.tm_min // 10 == 0 else tod.tm_min
                    print(f"Reset event at {tod.tm_hour}:{tod.tm_min} of {tod.tm_mday}/{tod.tm_mon}/{tod.tm_year}")

    def activate_buttons(self, set_active=True):
        self.reset_button.setDisabled(set_active)
        for cbox in self.check_box_list:
            cbox.setDisabled(set_active)


app = qwid.QApplication([])
button = ResetButton()
sys.exit(app.exec())
