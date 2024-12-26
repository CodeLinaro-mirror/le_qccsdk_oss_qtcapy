#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

class global_var:
    @staticmethod
    def _init():
        global _global_dict
        _global_dict = {}

    @staticmethod
    def set_value(key, value):
        _global_dict[key] = value

    @staticmethod
    def get_value(key):
        try:
            return _global_dict[key]
        except:
            print('Read'+key+'fail\r\n')