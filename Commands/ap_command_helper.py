# Copyright (c) 2020 Wi-Fi Alliance

# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.

# THE SOFTWARE IS PROVIDED 'AS IS' AND THE AUTHOR DISCLAIMS ALL
# WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
# CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
# FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF
# CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
# SOFTWARE.

# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import logging
import logging.handlers
from .command_helper import CommandHelper
from .shared_enums import CommandOperation, DebugLogLevel, BssIdentifierBand, WpsDeviceRole
from .command_interpreter import CommandInterpreter
from .command import Command
from datetime import datetime
from Commands.dut_logger import DutLogger, LogCategory
import os
from datetime import datetime
from .cli_helper import cli_serial_helper

logger = logging.getLogger('mylogger.cli_helper')

command_interpreter_obj = CommandInterpreter()
store_hostapd_config_for_debug = False
ap_debug_log_level = DebugLogLevel.DISABLE
hostapd_log_folder_path = "/var/log/hostapd.log"
hostapd_config_path = "/etc/hostapd/hostapd.conf"
hostapd_config_files = []


class ApCommandHelper:
    ap_config = {}
    store_test_artifcats = False

    @staticmethod
    def create_zephyr_sap_config(config: dict):
        ApCommandHelper.ap_config = config
        return None, None

    @staticmethod
    def get_existing_hostapd_conf():
        """Returns the existing hostapd configuration that was previously configured."""
        existing_config = {}
        if os.path.exists(hostapd_config_path):
            with open(hostapd_config_path) as file_reader:
                for each_line in file_reader:
                    key, val = each_line.split("=")
                    existing_config[key] = val.rstrip()
        return existing_config

    @staticmethod
    def get_hostapd_config(tlv_values: dict, interface_name: str, append_config_file: bool):
        """Returns the hostapd configurations from TLV's(type-length-value) to string that will be written into configuration file .

        Parameters
        ----------
        tlv_values : dict
            Configurations in TLVs
        interface_name:str
            Interface name to be configured.
        merge_config_file : bool
            Flag to indicate if new hostapd config file has to be create or the new config has to be merged into existing file
        """
        if interface_name is None:
            return None, "Unable to get interface name."
        if append_config_file:
            hostapd_config = (
                "bss=" + interface_name +"\nctrl_interface=/var/run/hostapd"
            )
        else:
            hostapd_config = (
                "ctrl_interface=/var/run/hostapd\nctrl_interface_group=0\ninterface=" + interface_name
            )
        has_sae = False
        has_wpa = False
        has_pmf = False
        has_owe = False
        has_transition = False
        band = None
        channel = None
        chwidth = 1
        enable_ax = enable_ac = False
        chwidthset = vht_chwidthset = False
        enable_muedca = False
        has_sae_groups = False
        enable_wps = False
        use_mbss = False
        for tlv_value in tlv_values:
            if tlv_value == "wpa_key_mgmt" and "SAE" in tlv_values[tlv_value] and "WPA-PSK" in tlv_values[tlv_value]:
                has_transition = True
            if tlv_value == "wpa_key_mgmt" and "OWE" in tlv_values[tlv_value]:
                has_owe = True
            if tlv_value == "wpa_key_mgmt" and "SAE" in tlv_values[tlv_value]:
                has_sae = True
            if tlv_value == "wpa" and "2" in tlv_values[tlv_value]:
                has_wpa = True
            if tlv_value == "ieee80211w":
                has_pmf = True
            if tlv_value == "hw_mode":
                band = tlv_values[tlv_value]
            if tlv_value == "channel":
                channel = int(tlv_values[tlv_value])
            if tlv_value == "he_oper_chwidth":
                chwidth = int(tlv_values[tlv_value])
                chwidthset = True
            if tlv_value == "vht_oper_chwidth":
                chwidth = int(tlv_values[tlv_value])
                vht_chwidthset = True
            if tlv_value == "ieee80211ac" and "1" in tlv_values[tlv_value]:
                enable_ac = True
            if tlv_value == "ieee80211ax" and "1" in tlv_values[tlv_value]:
                enable_ax = True
            if tlv_value == "he_mu_edca":
                enable_muedca = True
            if tlv_value == "sae_groups":
                has_sae_groups = True
            if tlv_value == "bss_identifier":
                use_mbss = True
                continue
            if tlv_value == "wps_enable":
                wps_setting = CommandHelper.get_wps_settings(WpsDeviceRole.WPS_AP)
                enable_wps = True
                if tlv_values[tlv_value] == "1":
                    # Normal, set wps state and wps common settings
                    for cfg_item in wps_setting:
                        if cfg_item[2][0] == "1":
                            # OOB only
                            if cfg_item[0] == "wps_state":
                                hostapd_config += "\n" + cfg_item[0] + "=" + "2"
                        elif cfg_item[2][0] == "2":
                            # Common settings
                            hostapd_config += "\n" + cfg_item[0] + "=" + cfg_item[1]
                elif tlv_values[tlv_value] == "2":
                    # OOB, set all settings
                    DutLogger.log(LogCategory.INFO, "APUT Configure WPS: OOB.")
                    for cfg_item in wps_setting:
                        hostapd_config += "\n" + cfg_item[0] + "=" + cfg_item[1]
                else:
                    DutLogger.log(LogCategory.ERROR, "Unknown WPS TLV value: {}".format(tlv_values[tlv_value]))
                continue

            if tlv_value == "owe_transition_bss_identifier":
                bss_id = int(tlv_values[tlv_value])
                bss_band = bss_id & 0x0F
                identifier = (bss_id & 0xF0) >> 4
                owe_if = CommandHelper.get_interface_name(identifier)
                if not owe_if:
                    owe_if = CommandHelper.set_interface_bss_id(band=bss_band, bss_id=identifier)
                if owe_if:
                    hostapd_config += "\n" + "owe_transition_ifname" + "=" + owe_if
                    if has_owe:
                        hostapd_config += "\n" + "ignore_broadcast_ssid=1"
                else:
                    DutLogger.log(LogCategory.ERROR, "Can't find owe transition ifname")
            elif tlv_value == "transition_disable":
                hostapd_config += "\n" + tlv_value + "=" + hex(int(tlv_values[tlv_value]))
            elif tlv_value == "auth_algorithm":
                hostapd_config += "\n" + "auth_algs" + "=" + tlv_values[tlv_value]
            elif tlv_value == "he_mu_edca":
                hostapd_config += "\n" + "he_mu_edca_qos_info_param_count" + "=" + tlv_values[tlv_value]
            else:
                hostapd_config += "\n" + tlv_value + "=" + tlv_values[tlv_value]

        if not has_pmf:
            if has_transition:
                hostapd_config += "\nieee80211w=1"
            elif has_sae and has_wpa:
                hostapd_config += "\nieee80211w=2"
            elif has_owe:
                hostapd_config += "\nieee80211w=2"
            elif has_wpa:
                hostapd_config += "\nieee80211w=1"
        if has_sae:
            hostapd_config += "\nsae_require_mfp=1"
        # Note: if any new DUT configuration is added for sae_groups,
        # then the following unconditional sae_groups addition should be
        # changed to become conditional on there being no other sae_groups
        # configuration
        # e.g.:
            if not has_sae_groups:
                hostapd_config += "\nsae_groups=15 16 17 18 19 20 21"

        # Todo: Add 6G conf
        #Channel width configuration
        #Default: 20MHz in 2.4G(No configuration required) 80MHz in 5G
        if band == "a":
            if __class__.is_ht40plus_chan(channel):
                hostapd_config += "\nht_capab=[HT40+]"
            elif __class__.is_ht40minus_chan(channel):
                hostapd_config += "\nht_capab=[HT40-]"
            else:
                chwidth = 0    
            if chwidth > 0:
                center_freq = ApCommandHelper.get_center_freq_idx(channel, chwidth)
                if enable_ac:
                    if vht_chwidthset == False:
                        hostapd_config += "\nvht_oper_chwidth="+str(chwidth)
                    hostapd_config += "\nvht_oper_centr_freq_seg0_idx="+str(center_freq)
                if enable_ax:
                    if chwidthset == False:
                        hostapd_config += "\nhe_oper_chwidth="+str(chwidth)
                    hostapd_config += "\nhe_oper_centr_freq_seg0_idx="+str(center_freq)

        if enable_muedca:
            hostapd_config += "\nhe_mu_edca_qos_info_queue_request=1"
            hostapd_config += "\nhe_mu_edca_ac_be_aifsn=0"
            hostapd_config += "\nhe_mu_edca_ac_be_ecwmin=15"
            hostapd_config += "\nhe_mu_edca_ac_be_ecwmax=15"
            hostapd_config += "\nhe_mu_edca_ac_be_timer=255"
            hostapd_config += "\nhe_mu_edca_ac_bk_aifsn=0"
            hostapd_config += "\nhe_mu_edca_ac_bk_aci=1"
            hostapd_config += "\nhe_mu_edca_ac_bk_ecwmin=15"
            hostapd_config += "\nhe_mu_edca_ac_bk_ecwmax=15"
            hostapd_config += "\nhe_mu_edca_ac_bk_timer=255"
            hostapd_config += "\nhe_mu_edca_ac_vi_ecwmin=15"
            hostapd_config += "\nhe_mu_edca_ac_vi_ecwmax=15"
            hostapd_config += "\nhe_mu_edca_ac_vi_aifsn=0"
            hostapd_config += "\nhe_mu_edca_ac_vi_aci=2"
            hostapd_config += "\nhe_mu_edca_ac_vi_timer=255"
            hostapd_config += "\nhe_mu_edca_ac_vo_aifsn=0"
            hostapd_config += "\nhe_mu_edca_ac_vo_aci=3"
            hostapd_config += "\nhe_mu_edca_ac_vo_ecwmin=15"
            hostapd_config += "\nhe_mu_edca_ac_vo_ecwmax=15"
            hostapd_config += "\nhe_mu_edca_ac_vo_timer=255"

        if enable_wps:
            if use_mbss:
               hostapd_config += "\nwps_rf_bands=ag"
            else: 
                if band == "a":
                    hostapd_config += "\nwps_rf_bands=a"
                elif band == "g":
                    hostapd_config += "\nwps_rf_bands=g"

        '''
        if merge_config_file:
            appended_hostapd_conf_str = ""
            existing_conf = ApCommandHelper.get_existing_hostapd_conf()
            hostapd_config_dict = ApCommandHelper.__convert_config_str_to_dict(config=hostapd_config)
            for each_key in existing_conf:
                if each_key not in hostapd_config_dict:
                    hostapd_config_dict[each_key] = existing_conf[each_key]
            for each_hostapd_conf in hostapd_config_dict:
                appended_hostapd_conf_str += each_hostapd_conf + "=" + hostapd_config_dict[each_hostapd_conf] + "\n"
            hostapd_config = appended_hostapd_conf_str.rstrip()
        '''

        hostapd_config += "\n"
        return hostapd_config, None

    @staticmethod
    def __convert_config_str_to_dict(config: str):
        """Converting string into dictionary using dict comprehension
        Parameters
        -----------
        config : [str]
            Converts the configuration from datatype string to dictionary.
        """
        config_dict = dict(each_config.split("=") for each_config in config.split("\n"))
        return config_dict


    @staticmethod
    def ap_start_up():
        """Starts the hostapd service on the AP."""
        #ApCommandHelper.store_test_artifcats = True
        debug_log_level = ApCommandHelper.__get_ap_debug_log_level()
        now = datetime.now()
        dt_string = now.isoformat()
        if ApCommandHelper.ap_config is None:
            return None, "Fail to Read AP configuration."
        security = ""
        psk = ""
        ssid = ApCommandHelper.ap_config["ssid"]
        ch = ApCommandHelper.ap_config["channel"]
        if "wpa_key_mgmt" in ApCommandHelper.ap_config:
            security = ApCommandHelper.ap_config["wpa_key_mgmt"]
        if "wpa_passphrase" in ApCommandHelper.ap_config:
            psk = ApCommandHelper.ap_config["wpa_passphrase"]

        ApCommandHelper.__killall_hostapd()
        if security == "WPA-PSK":
            ap_command = "wifi ap enable -s {} -c {} -p {} -k 1".format(ssid, ch, psk)
        elif not psk or not security:
            ap_command = "wifi ap enable -s {} -c {} ".format(ssid, ch)
        else:
            return "Unknown options.", "Check the AP_CONFIG."
            
        ret = cli_serial_helper.execute_and_search(ap_command, "AP enabled")
        if ret:
            return "Success to configure SAP in Zephyr.", None
        else:
            return None, "Fail to configure SAP in Zephyr."

    @staticmethod
    def ap_stop():
        CommandHelper.clear_bss_identifiers()
        """Stops the hostapd service on the AP."""
        global hostapd_config_files
        if ApCommandHelper.store_test_artifcats:
            ApCommandHelper.store_test_artifcats = False
        hostapd_config_files = []
        status = ApCommandHelper.check_hostapd_is_active()
        if status:
            cli_serial_helper.execute("wifi ap disable")
            status = ApCommandHelper.check_hostapd_is_active()
            if not status:
                return "Already stop AP in Zephyr.", None
            else:
                return None, "Unable to stop AP in Zephyr."
        else:
            return "Already stop AP in Zephyr.", None

    @staticmethod
    def __log_hostapd_logs():
        """Logs the hostapd debug logs into a text file for debug."""
        global ap_debug_log_level
        if ap_debug_log_level != DebugLogLevel.DISABLE :
            if os.path.exists(hostapd_log_folder_path):
                with open(hostapd_log_folder_path, "r") as file_reader:
                    file_content = file_reader.readlines()
                    if file_content:
                        DutLogger.log(LogCategory.DEBUG, "Hostapd logs :" + str(file_content))
            else:
                DutLogger.log(LogCategory.DEBUG, "Hostapd debug log file is not found at {}".format(hostapd_log_folder_path))

    @staticmethod
    def __get_ap_debug_log_level():
        global ap_debug_log_level
        if ap_debug_log_level == DebugLogLevel.BASIC:
            return "-dK"
        elif ap_debug_log_level == DebugLogLevel.ADVANCED:
            return "-dddK"
        else:
            return None

    @staticmethod
    def set_ap_debug_log_level(log_level):
        global ap_debug_log_level
        ap_debug_log_level = log_level

    @staticmethod
    def check_hostapd_is_active():
        """Utility method to check if hostapd service is active

        Returns
        -------
        bool
            Boolean representing if hostapd service is active or not.
        """
        res = cli_serial_helper.execute_and_search("wifi ap status", "State: ENABLED")
        if res:
            return True
        else:
            DutLogger.log(LogCategory.DEBUG, "AP is inactive.")
            return False

    @staticmethod
    def __killall_hostapd():
        cli_serial_helper.execute("wifi ap disable")

    @staticmethod
    def get_ap_if_status(if_name):
        hostapd_cli_status, _ = CommandHelper.run_shell_command(
            "sudo hostapd_cli -i {} status".format(if_name)
        )
        interface_freq = command_interpreter_obj.apply_cmd_regex(
            Command.GET_FREQ, hostapd_cli_status
        )
        interface_ssid = command_interpreter_obj.apply_cmd_regex(
            Command.GET_AP_SSID, hostapd_cli_status
        )
        mac_addr = command_interpreter_obj.apply_cmd_regex(
            Command.GET_AP_DUT_MAC_ADDR, hostapd_cli_status
        )
        return interface_freq, interface_ssid, mac_addr

    @staticmethod
    def get_center_freq_idx(chan, width: int = 1):
        if (width == 1):
            if chan >= 36 and chan <= 48:
                return "42"
            elif chan <= 64:
                return "58"
            elif chan >= 100 and chan <= 112:
                return "106"
            elif chan <= 128:
                return "122"
            elif chan <= 144:
                return "138"
            elif chan >= 149 and chan <= 161:
                return  "155"
        elif (width == 2):
            if chan >= 36 and chan <= 64:
                return "50"
            elif chan >= 100 and chan <= 128:
                return "114"

    @staticmethod
    def is_ht40plus_chan(chan):
        if (chan == 36 or chan == 44 or chan == 52 or chan == 60 or
            chan == 100 or chan == 108 or chan == 116 or chan == 124 or
            chan == 132 or chan == 140 or chan == 149 or chan == 157):
            return True
        else:
            return False

    @staticmethod
    def is_ht40minus_chan(chan):
        if (chan == 40 or chan == 48 or chan == 56 or chan == 64 or
            chan == 104 or chan == 112 or chan == 120 or chan == 128 or
            chan == 136 or chan == 144 or chan == 153 or chan == 161):
            return True
        else:
            return False

    '''
    @staticmethod
    def store_bss_identifiers(bss_identifier: int, ssid: str, interface_name):
        global bss_identifiers
        bss_identifiers[bss_identifier] = (ssid, interface_name)

    @staticmethod
    def get_bss_identifier_details(identifier: int):
        global bss_identifiers
        if identifier in bss_identifiers:
            return bss_identifiers[identifier]
        return None, None

    @staticmethod
    def get_bss_identifiers():
        global bss_identifiers
        return bss_identifiers
    '''

    @staticmethod
    def send_ap_disconnect(address):
        if_name = CommandHelper.get_interface_name()
        reason = "reason=1"
        return CommandHelper.run_shell_command(
            ("sudo hostapd_cli -i {} disassociate {} {}").format(if_name, address, reason)
        )
    
    @staticmethod
    def ap_chan_switch(channel, freq):
        if_name = CommandHelper.get_interface_name()
        center_freq = 5000 + int(__class__.get_center_freq_idx(int(channel))) * 5
        if center_freq == int(freq) + 30 or center_freq == int(freq) - 10:
            offset = 1
        else:
            offset = -1
        return CommandHelper.run_shell_command(
            ("sudo hostapd_cli -i {} chan_switch 10 {} center_freq1={} sec_channel_offset={} bandwidth=80 vht").format(if_name, freq, center_freq, offset)
        )

    @staticmethod
    def send_ap_btm_req(bssid, disassoc_immi, cand_list, disassoc_timer, retry_delay, bss_term_bit, bss_term_tsf, bss_term_duration):
        param_str = ""
        if disassoc_immi:
            param_str += " disassoc_imminent={}".format(disassoc_immi)
        if cand_list:
            if int(cand_list) == 1:
                param_str += " pref=1"
        if disassoc_timer:
            param_str += " disassoc_timer={}".format(disassoc_timer)
        if retry_delay:
            param_str += " mbo=0:{}:0".format(retry_delay)

        # ToDo: BSS termination is not yet finished
        if bss_term_bit and bss_term_tsf and bss_term_duration:
            param_str += " bss_term={},{}".format(bss_term_tsf, bss_term_duration)        
        DutLogger.log(LogCategory.DEBUG, "ap_btm_req param: {}".format(param_str))
        interface_name = CommandHelper.get_interface_name()

        return command_interpreter_obj.execute(
            Command.SEND_AP_BTM_REQ.value,
            [interface_name, bssid, param_str],
        )

    @staticmethod
    def set_ap_param(param_str, value):
        if_name = CommandHelper.get_interface_name()

        return  command_interpreter_obj.execute(
            Command.SET_AP_PARAM.value,
            [if_name, param_str, value],
        )

    @staticmethod
    def get_wsc_cred():
        # Get SSID, key_mgmt and Passphrase from config file
        key_list = ["ssid=", "wpa_passphrase=", "wpa_key_mgmt="]
        config_list = []
        file_path = "/etc/hostapd/{}".format(hostapd_config_files[0])
        with open(file_path, "r") as config_f:
            config =config_f.read()
            for key in key_list:
                index = config.find(key)
                if index == -1:
                    DutLogger.log(LogCategory.INFO, "Cannot find the setting: {}".format(key))
                    config_list.append("")
                else:
                    index += len(key)
                    if config[index] == '\"':
                        #  the format aaaaa="xxxxxxxx"
                        index += 1
                        end = config[index:].find('\"')
                    else:
                        # the format bbbbb=yyyyyyyy
                        end = config[index:].find('\n')
                    config_list.append(config[index:index+end])
        return config_list, None

    @staticmethod
    def ap_start_wps(pin_code):
        if_name = CommandHelper.get_interface_name()
        if pin_code is not None:
            # Verify invalid PIN code
            if os.path.exists("/tmp/pin_checksum.sh"):
                std_out, std_err = CommandHelper.run_shell_command("/tmp/pin_checksum.sh {}".format(pin_code))
            else:
                std_out = "1"
            if std_out and int(std_out):
                return CommandHelper.run_shell_command(
                    ("sudo hostapd_cli -i {} wps_pin any {}").format(if_name, pin_code)
                )
            else:
                error = "AP detects invalid PIN code"
                DutLogger.log(LogCategory.ERROR, "Invalid PIN code :" + pin_code)
                return "Failed", error
        else:    
            return CommandHelper.run_shell_command(
                ("sudo hostapd_cli -i {} wps_pbc").format(if_name)
            )

    @staticmethod
    def ap_configure_wsc(config_enums: dict):
        __class__.ap_stop()
        config_only = config_enums.pop("wsc_config_only", None)
        ApCommandHelper.assign_interface_and_config_file_name(config_enums)
        __class__.create_hostapd_config(config_enums, False)
        if config_only is not None:
            return "Configure wsc ap successfully. (Configure only)", None
        
        __class__.ap_start_up()
        return "Confiugre and start wsc ap successfully. (Configure and start)", None

    @staticmethod
    def get_wsc_pin():
        if_name = CommandHelper.get_interface_name()

        return CommandHelper.run_shell_command(
            ("sudo hostapd_cli -i {} wps_ap_pin get").format(if_name)
        )

    @staticmethod
    def assign_interface_and_config_file_name(config: dict):
        pass

    @staticmethod
    def ap_configure(config: dict):
        # Parse BSS_IDENTIFIER TLV in multiple WLANs case
        return ApCommandHelper.create_zephyr_sap_config(config)