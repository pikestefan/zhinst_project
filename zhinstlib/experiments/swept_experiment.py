from zhinstlib.core_classes.zinst_device import ziVirtualDevice
from zhinstlib.helpers.helper_funcs import get_device_props
import time
import numpy as np


class swept_experiment(object):
    def __init__(self, lin_settings, exp_settings, opt_settings, save_settings):

        self.lin_settings = lin_settings
        self.exp_settings = exp_settings
        self.opt_settings = opt_settings
        self.save_settings = save_settings

