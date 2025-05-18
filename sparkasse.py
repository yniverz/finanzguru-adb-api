

import threading
import time
from ppadb.device import Device
import xml.etree.ElementTree as ET
import adb
from helpers import print


class SparkasseClient:
    def __init__(self, adb_device: Device = None, app_pin: str = None):
        """
        Initialize the SparkassrClient with an ADB device.
        If no device is provided, it will use the first available device.

        As Sparkasse requires an app pin, the PIN is needed
        """
        self.adb_client = adb.Adb(adb_device, "C:\\Program Files\\Nox\\bin\\adb.exe")
        self.app_pin = app_pin

    def init_app(self):
        """
        Start the Sparkasse app.
        Recommended to use this method after some time with no activity in the app.
        """

        self.adb_client.close_app("com.starfinanz.smob.android.sfinanzstatus")

        self.adb_client.open_app("com.starfinanz.smob.android.sfinanzstatus", ".LauncherActivity")

        self.adb_client.input_text(self.app_pin)
        self.adb_client.click(400, 1400)

        print("Waiting for Sparkasse to load...")
        time.sleep(30)
        
    def is_overview(self) -> bool:
        """
        :return: True if übersicht is open
        """

        elements = self.adb_client.screencap_text()
        for element in elements:
            if "Total amount" in element.text:
                return True
        
        return False
    
    def ensure_overview(self):
        print("Scroll to top / Übersicht")
        if not self.is_overview():
            print("Not in Übersicht, reopening app...")
            self.init_app()

    def open_widget_by_name(self, name: str):
        print("Looking for '"+name+"' item")

        self.ensure_overview()

        element = self.adb_client.find_element_by_scroll(name, from_screencap=True)
        if not element:
            raise Exception("Element not found")
        
        self.adb_client.click_element(element)

        time.sleep(8)

    
    def request_bank_update(self, block: bool = True) -> bool:
        """
        Request an update for all ankaccounts accounts
        :param block: if True, the function will block until the update is finished
        :return: True if the update was requested, False if it was already requested in the last 30 minutes
        """

        if not block:
            thread = threading.Thread(target=self.request_bank_update, args=(True,))
            thread.start()
            return True

        self.ensure_overview()

        print("Requesting bank update")
        self.adb_client.device.shell("input swipe 500 400 500 1400 500")
        print("Waiting 30 seconds for update to finish...")
        time.sleep(10)

        return True
    
    def transfer_money(self, amount: float, target_iban: str, target_name: str, memo: str = None):
        """
        Transfer money to another account
        :param amount: amount to transfer
        :param to_account: account to transfer to
        """

        self.ensure_overview()

        self.look_and_click("Send")
        time.sleep(5)

        self.look_and_click("Standard")
        time.sleep(5)

        self.look_and_click("recipient")
        time.sleep(2)

        self.adb_client.input_text(target_iban)
        time.sleep(2)

        self.look_and_click("Import")
        time.sleep(2)

        self.look_and_click("Payee")
        time.sleep(2)

        self.adb_client.input_text(target_name)
        time.sleep(2)

        self.look_and_click("Next")
        time.sleep(2)

        self.adb_client.input_text(str(int(amount * 100)))
        time.sleep(2)

        if memo:
            self.look_and_click("Memo")
            time.sleep(2)

            self.adb_client.input_text(memo)
            time.sleep(2)

        self.look_and_click("Next")
        time.sleep(2)

        self.look_and_click("real-time")
        time.sleep(2)

        self.look_and_click("Verify")
        time.sleep(2)

        self.look_and_click("Next")


    def look_and_click(self, name: str):
        element = self.adb_client.find_element_by_scroll(name, from_screencap=True)
        if not element:
            raise Exception("Element not found")
        
        self.adb_client.click_element(element)