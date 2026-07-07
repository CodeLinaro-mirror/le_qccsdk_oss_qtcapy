#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================
import time
import re
import serial
import threading
import logging
import logging.handlers
from .global_var import global_var

logger = logging.getLogger('mylogger.cli_helper')
logger.debug("cli_helper test\r\n")

class CLI_Helper:
    def __init__(self,serialPort):
        #Min delay on reading serial continuous characters for serial.readlines()
        #For example, 'mstop' prints continuous chars 1ms*100=0.1s between '.', if TIMEOUT_S=0.15, then readlines() will hung
        self.TIMEOUT_S = 0.08
        self.WRITE_CHAR_DELAY_S = 0.1
        self.port = serialPort
        self.baudrate = 115200
        self.dutCrashTag  = 0
        try:
            self.serialhandle = serial.Serial(self.port, self.baudrate, timeout = self.TIMEOUT_S)
            self.exitRead     = 0
        except:
            self.serialhandle.close()
            self.serialhandle = serial.Serial(self.port, self.baudrate, timeout = self.TIMEOUT_S)

    def open_serial(self):
        self.serialhandle.open()

    def close_serial(self):
        self.serialhandle.close()

    def clear_buffer(self):
        self.serialBuffer = ""

    def get_buffer(self):
        return self.serialBuffer

    def read_serial(self):
        readList = ""
        logs = ""

        try:
            readList = self.serialhandle.readlines()
        except:
            pass

        if len(readList) > 0:
            for line in readList:
                reading = str(line, encoding = "ISO-8859-1")
                logs = logs + reading

            if (logs != ""):
                self.serialBuffer += logs

        logger.info("[DUT_BUFFER] %s <-------- %s", self.port, logs)

    def write_bytes(self, command):
        #make sure '\r' output successfully
        for cmdbyte in (command+'\r'):
            time.sleep(self.WRITE_CHAR_DELAY_S)
            self.serialhandle.write(cmdbyte.encode())

    def writeSerial(self, command):
        logger.info("[DUT_CLI] %s --------> %s", self.port, command)
        retryTimes  = 0
        try_max_cnt = 80
        #Clear Buffer
        self.clear_buffer()

        #Serial Write
        self.write_bytes(command)

        #Check Result
        while 1:
            time.sleep(0.1)
            self.read_serial()

            if re.search('~\$', self.serialBuffer, re.M):
                break
            else:
                self.serialhandle.write("\r".encode())
                retryTimes  = retryTimes + 1

            if retryTimes == try_max_cnt:
                logger.error("Max Retry times, please check DUT serial!!!")
                self.dutCrashTag = 1
                break

        return self.serialBuffer

    def writeSerialQuick(self,command):
        logger.info("[DUT_CLI] %s --------> %s", self.port, command)

        #Clear Buffer
        self.clear_buffer()

        #Serial Write
        self.write_bytes(command)
        time.sleep(0.1)
        # self.read_serial()
        self.serialhandle.reset_input_buffer()

    def readSerialbuffer(self):
        self.read_serial()

        return self.serialBuffer

    def checkdutCrashTag(self):
        tag = self.dutCrashTag
        return tag

class cli_serial_helper:
    serial = None

    @classmethod
    def init(cls, serial_port):
        if cls.serial == None:
            cls.serial = CLI_Helper(serial_port)
        if not cls.serial.serialhandle.is_open:
            logger.error("Open %s fail.", port)

    @classmethod
    def execute(cls, command):
        return cls.serial.writeSerial(command)

    @classmethod
    def execute_and_search(cls, command, pattern):
        output = cls.serial.writeSerial(command)
        return re.search(pattern, output)

    @classmethod
    def execute_and_wait_until(cls, command, pattern, timeout=5):
        output = cls.serial.writeSerial(command)
        expire_time = time.time() + timeout
        while time.time() < expire_time:
            time.sleep(0.2)
            output = cls.serial.readSerialbuffer()
            if re.search(pattern, output, re.M):
                return output
        return None
