#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================
import time
import re
import os
import serial
import threading
import logging
import logging.handlers
from .cli_helper import CLI_Helper
from Commands.command_helper import CommandHelper

logger = logging.getLogger('mylogger.QCC730')
logger.info("[DUT_LOG] QCC730 test\r\n")

class QCC730_Command:
    def  __init__(self, uart_port):
        self.dutCrashTag  = 0
        self.ser = CLI_Helper(uart_port)

    def clearDutBuffer(self):
        dutOutput = ser.readSerialbuffer()
        return dutOutput

    def runCLIQuick(self,command):
        dutOutput = ser.writeSerialQuick(command)
        # wait for serial output complete
        time.sleep(0.05)

    def initReset(self):
        self.enterDir("platform")
        dutOutput = self.ser.writeSerial("reset")
        return dutOutput

    def enableWireless(self):
        self.enterDir("WLAN")
        dutOutput = self.ser.writeSerial("enable")
        return dutOutput

    def getVersion(self):
        self.enterDir("root")
        dutOutput = ser.writeSerial("ver")
        pattern   = "crm num: (.*)"
        dutOutput    = self.getMatchingInfo(pattern,dutOutput,1)
        return dutOutput

    def getBssid(self):
        self.enterDir("WLAN")
        dutOutput = ser.writeSerial("info")
        pattern   = "Mac Addr(\s+)=(\s+)(([0-9A-F]{1,2}[:]){5}[0-9A-F]{1,2})"
        bssid    = self.getMatchingInfo(pattern,dutOutput,3)
        return bssid

    def getMacAddr(self):
        self.enterDir("WLAN")
        dutOutput = self.ser.writeSerial("info")
        pattern   = r"Mac Addr\s*=\s*([0-9a-fA-F:]+)"
        disable = "Enable WLAN before get the WLAN infomation"
        match     = re.search(pattern, dutOutput)
        macAddr = ""
        if match:
            macAddr = match.group(1)
            print("MAC Address:", macAddr)
        elif disable in dutOutput:
            dutOutput = self.ser.writeSerial("enable")
            match     = re.search(pattern, dutOutput)
            if match:
                macAddr = match.group(1)
            else:
                print("MAC Address not found")
        else:
            print("MAC Address not found")
        return macAddr

    def getDutConnectStatus(self):
        self.enterDir("WLAN")
        dutOutput = self.ser.writeSerial("info")
        if re.search("ssid(\s+)=(\s+)",dutOutput):
            return 1
        else:
            return 0

    def getIPconfig(self,wirelessInterface):
        self.enterDir("net")
        dutOutput = self.ser.writeSerial("ifconfig %s" %wirelessInterface)
        pattern   = "IPv4:(\s+)(\d+.\d+.\d+.\d+)(\s+)Subnet Mask: (\d+.\d+.\d+.\d+)(\s+)Default Gateway:(\s+)(([0-9]{1,3}[.]){3}[0-9]{1,3})"
        ip         = None
        netmask    = None
        dns        = None
        gateway    = None

        ip         = self.getMatchingInfo(pattern,dutOutput,2)
        netmask    = self.getMatchingInfo(pattern,dutOutput,4)
        gateway    = self.getMatchingInfo(pattern,dutOutput,7)
        self.dutIp = ip
        return ip

    def trafficReset(self):
        self.enterDir("wificert")
        self.ser.writeSerialQuick("udpquit")
        # wait for the RX/TX traffic result.
        time.sleep(1.5)
        dutOutput = self.ser.readSerialbuffer()
        return True

    def setPrivatekey(self,psk):
        dutOutput = self.ser.writeSerial("SetWpaPassPhrase %s" %(str(psk)))
        return dutOutput

    def setSecurity(self,key_mgmt="WPA-PSK",proto="RSN",pairwise="CCMP",group="CCMP"):
        if (re.match('^TKIP$',pairwise,re.I) or re.match('^TKIP$',group,re.I)):
            dutEncpType = "TKIP"
        elif (re.match('^CCMP$',pairwise,re.I) or re.match('^CCMP$',group,re.I)):
            dutEncpType = "CCMP"
        else:
            if (re.match('^RSN$',proto,re.I)):
                dutEncpType = "CCMP"
            elif (re.match('^WPA$',proto,re.I)):
                dutEncpType = "TKIP"
            else:
                dutEncpType = "CCMP"

        if (re.match('^RSN$',proto,re.I)):
            if (re.match('^SAE WPA-PSK$',key_mgmt,re.I)):
                dutkeymgmttype = "SAE_WPA2"
            elif (re.match('^SAE$',key_mgmt,re.I)):
                dutkeymgmttype = "SAE"
            else:
                dutkeymgmttype = "WPA2"
        elif (re.match('^WPA$',proto,re.I)):
            dutkeymgmttype = "WPA"
        else:
            dutkeymgmttype = "WPA2"

        dutOutput = self.ser.writeSerial("SetWpaParameters %s %s %s" %(dutkeymgmttype,dutEncpType,dutEncpType))
        return dutOutput

    def connectAp(self,ssid):
        self.enterDir("WLAN")
        self.ser.writeSerial("connect %s" %ssid)
        dutOutput = self.getDutConnectStatus()
        return dutOutput

    def disconnectAp(self):
        self.enableWireless()
        self.ser.writeSerial("disconnect")
        if self.getDutConnectStatus():
            return None, "cannot disconnect"
        else:
            return "disconnect successfully", None

    def setStaticIp(self,ip,mask,gateway,):
        self.enterDir("net")
        interface = CommandHelper.get_interface_name()
        print(interface,ip,mask,gateway)
        dutOutput = self.ser.writeSerial("ifconfig %s %s %s %s" %(interface,ip,mask,gateway))
        match = re.search(r"Received IP address: (\d{1,3}(?:\.\d{1,3}){3})", dutOutput)

        if match:
            extractedIp = match.group(1)
            print(f"Extracted IP address: {extractedIp} IP is {ip}")

            if extractedIp == ip:
                print("The extracted IP address matches the configured IP address.")
                return True
            else:
                print("The extracted IP address does not match the configured IP address.")
        else:
            print("No IP address found in the dutOutput.")      
        return False

    def configUdpRx(self, interface, sourcePort, echo):
        # self.enterDir("wificert")
        self.ser.writeSerial("root")
        self.ser.writeSerial("wificert")
        commandLine = "udp -s -B "+ interface + " -e -p " + sourcePort
        self.ser.writeSerial(commandLine)
        return None

    def getMatchingInfo(self,pattern,dutOutput,feedbackLocation = 0):
        matchInfo = ""
        m = re.search(pattern,dutOutput,re.I)
        if m is not None:
            matchInfo = m.group(feedbackLocation)
        return matchInfo

    def enterDir(self,dir):
        self.ser.writeSerialQuick("root")
        self.ser.writeSerialQuick(dir)
        return None