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
from zhinstlib.helpers.helper_funcs import get_device_props
from zhinstlib.core.zinst_device import ziVirtualDevice
import time


class TurnOffPID_btn(qwid.QWidget):
    def __init__(self, *args, **kwargs):
        super(TurnOffPID_btn, self).__init__(*args, **kwargs)

        self.zinst_dev = None
        self.connected = False

        layout = qwid.QVBoxLayout()

        self.text_edit = qwid.QLineEdit("dev5152")
        layout.addWidget(self.text_edit)

        self.connect_button = qwid.QPushButton(text="Connect to device")
        self.connect_button.clicked.connect(self.connect_to_dev)
        layout.addWidget(self.connect_button)

        hlayout = qwid.QHBoxLayout()
        hlayout2 = qwid.QHBoxLayout()
        self.btn_list = []
        self.txt_edit_list = []
        for ii in range(4):
            loc_pushbtn = qwid.QPushButton(text=f"PID {ii}")
            loc_pushbtn.setCheckable(True)
            loc_pushbtn.setText(f"PID {ii}")
            loc_pushbtn.clicked.connect(self.turn_off_pids)
            hlayout.addWidget(loc_pushbtn)
            self.btn_list.append(loc_pushbtn)

            loc_ledit = qwid.QLineEdit("0")
            hlayout2.addWidget(loc_ledit)
            self.txt_edit_list.append(loc_ledit)
        layout.addLayout(hlayout)
        layout.addLayout(hlayout2)

        self.setLayout(layout)
        self.setObjectName("PID reset button")
        self.show()

    @qcore.pyqtSlot()
    def connect_to_dev(self):
        if not self.connected:
            device_id = self.text_edit.text()
            props = get_device_props(device_id)

            dev = ziVirtualDevice(
                device_id,
                props["serveraddress"],
                props["serverport"],
                props["apilevel"],
            )

            if dev is not None:
                self.connected = True
                self.zinst_dev = dev
                print("Connected.")
                self.text_edit.setDisabled(True)
                self.connect_button.setDisabled(True)
        else:
            print("Already connected.")

    @qcore.pyqtSlot(bool)
    def turn_off_pids(self, value):
        btn_object = self.sender()
        pid_num = int(btn_object.text()[-1])

        if value:
            self.zinst_dev.set_pid_enabled(pid_num, True)
        else:
            self.zinst_dev.set_pid_enabled(pid_num, False)
            default_value = self.txt_edit_list[pid_num].text()
            self.zinst_dev.set_aux_offset(pid_num, float(default_value))


app = qwid.QApplication([])
button = TurnOffPID_btn()
sys.exit(app.exec())
