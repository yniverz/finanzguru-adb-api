

import threading
import time
from ppadb.device import Device
import xml.etree.ElementTree as ET
import adb
from helpers import print


class FinanzGuruClient:
    def __init__(self, adb_device: Device = None, device_pin: str = None):
        """
        Initialize the FinanzGuruClient with an ADB device.
        If no device is provided, it will use the first available device.

        As FinanzGuru is ususally protected by the device login, the PIN is needed
        """
        self.adb_client = adb.Adb(adb_device)
        self.device_pin = device_pin

        self.last_bank_update = 0

    def init_app(self):
        """
        Start the FinanzGuru app.
        Recommended to use this method after some time with no activity in the app.
        """

        self.adb_client.close_app("de.dwins.financeguru")

        self.adb_client.open_app("de.dwins.financeguru", ".MainActivity")

        if self.device_pin:
            self.adb_client.input_text(self.device_pin)

        print("Waiting for Finanzguru to load...")
        time.sleep(30)
        
    def is_overview(self) -> bool:
        """
        :return: True if übersicht is open
        """

        root = self.adb_client._get_current_xml()

        elements = root.findall(".//*[@text]")
        for element in elements:
            index = element.attrib["index"]
            text = element.attrib["text"]
            if text == "Übersicht" and index == "0":
                return True
        
        return False
    
    def scroll_to_top_overview(self):
        print("Scroll to top / Übersicht")
        if not self.is_overview():
            print("Not in Übersicht, reopening app...")
            self.init_app()

        if not hasattr(self, "overview_button"):
            elements = self.adb_client.get_elements_by_text("Übersicht")
            
            elements = [e for e in elements if e.element.attrib.get("clickable") == "true"]
            if len(elements) == 0:
                raise Exception("No clickable elements found with text 'Übersicht'")
            
            # click on center of the last element
            element = elements[-1]

            self.overview_button = element

        self.adb_client.click_element(self.overview_button)
        time.sleep(3)

    def open_widget_by_name(self, name: str):
        print("Looking for '"+name+"' item")

        self.scroll_to_top_overview()

        element = self.adb_client.find_element_by_scroll(name)
        widget = element.element

        if widget == False:
            print(f"Widget '{name}' not found, restarting...")
            return False

        bounds = self.adb_client.get_center_of_element(element)

        self.adb_client.click(580, bounds[1])

        time.sleep(8)


    def add_transaction(self, amount: float, name: str, category: str):
        """
        Adds a transaction
        
        requires transactions window to be open
        """

        if amount == 0:
            return False

        self.adb_client.device.shell("input tap 610 1400")
        time.sleep(5)

        if amount < 0:
            pass
            # self.device.shell("input tap 270 220")
        else:
            # self.device.shell("input tap 430 220")
            self.adb_client.device.shell("input tap 80 260")
        time.sleep(5)

        # self.device.shell("input tap 350 350")
        self.adb_client.device.shell("input tap 350 260")
        time.sleep(5)

        amount_cents = str(int(round(abs(amount)*100)))
        self.adb_client.device.shell("input text "+str(amount_cents))
        time.sleep(5)

        # self.device.shell("input tap 350 530")
        self.adb_client.device.shell("input tap 350 425")
        time.sleep(5)

        self.adb_client.input_text(name)
        time.sleep(8)

        self.adb_client.device.shell("input tap 350 630")
        time.sleep(8)

        # # check if text "alle ausklappen" is visible
        # el = self.find_element_by_text("alle ausklappen")
        # if el != False:
        #     self.device.shell("input tap 150 180")
        #     time.sleep(5)

        self.adb_client.device.shell("input tap 370 100")
        time.sleep(5)

        self.adb_client.input_text(category)
        time.sleep(2)

        self.adb_client.device.shell("input tap 300 240")
        time.sleep(6)

        self.adb_client.device.shell("input tap 350 1460")
        time.sleep(25)


    def get_account_current_app_balance(self, account_name: str) -> tuple[float, adb.BasicElement]:
        self.scroll_to_top_overview()

        _ = self.adb_client.find_element_by_scroll(text=account_name)

        elements, _ = self.adb_client.get_list_of_elements()
        # find index of element with text == account_name
        index = -1
        for i, element in enumerate(elements):
            if element.text == account_name:
                index = i
                break
        if index == -1:
            print(f"Error: Element with text '{account_name}' not found")
            return False
        # get the next element
        next_element = elements[index + 1]
        # get the text of the next element
        text = next_element.text
        # remove the last 2 characters
        text = text[:-2]
        # replace "." with "" and "," with "."
        text = text.replace(".", "")
        text = text.replace(",", ".")
        # convert to float
        amount = float(text)

        print(f"Current balance of {account_name} is {amount:.2f} euro")

        return amount, element

    
    def update_account_balance(self, account_name: str, new_balance: float, threshhold: float = 0) -> bool:
        amount, element = self.get_account_current_app_balance(account_name)

        difference = round(new_balance - amount, 2)

        if abs(difference) <= threshhold:
            print(f"Balance change within {threshhold} euro ({abs(difference):.2f}), ignoring")
            return False
        
        self.adb_client.click_element(element)

        print(f"Balance change of {difference:.2f} euro, adding transaction")
        self.add_transaction(
            difference, 
            ("Gain" if difference > 0 else "Loss"),
            "Trading Verlust" if difference < 0 else "Trading Gewinn"
        )

        print("return back to main menu")
        self.adb_client.back_keyevent()

    def request_bank_update(self, block: bool = True) -> bool:
        """
        Request an update for all ankaccounts accounts
        :param block: if True, the function will block until the update is finished
        :return: True if the update was requested, False if it was already requested in the last 30 minutes
        """

        if time.time() - self.last_bank_update < 60*60*30:
            print("Bank update already requested in the last 30 minutes, skipping")
            return False
        
        self.last_bank_update = time.time()

        if not block:
            thread = threading.Thread(target=self.request_bank_update, args=(True,))
            thread.start()
            return True

        self.scroll_to_top_overview()

        print("Requesting bank update")
        self.adb_client.device.shell("input swipe 500 400 500 1400 500")
        print("Waiting 30 seconds for update to finish...")
        time.sleep(30)

        return True