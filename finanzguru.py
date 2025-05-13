

import json
import time
from ppadb.device import Device
from . import adb


class FinanzGuruClient:
    def __init__(self, adb_device: Device = None, device_pin: str = None):
        """
        Initialize the FinanzGuruClient with an ADB device.
        If no device is provided, it will use the first available device.

        As FinanzGuru is ususally protected by the device login, the PIN code is needed
        !!! ONLY WORKS WITH NUMBER PIN CODES !!!
        """
        self.adb_client = adb.Adb(adb_device)
        self.device_pin = device_pin

    def init_app(self):
        """
        Start the FinanzGuru app.
        Recommended to use this method after some time with no activity in the app.
        """

        self.adb_client.close_app("de.dwins.financeguru")

        self.adb_client.open_app("de.dwins.financeguru", ".MainActivity")

        if self.device_pin:
            for digit in self.device_pin:
                self.adb_client.device.shell(f"input keyevent KEYCODE_{digit}")

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
    
    def _scroll_to_top_overview(self):
        elements = self.adb_client.find_elements_by_text("Übersicht")
        
        elements = [e for e in elements if e.attrib.get("clickable") == "true"]
        if len(elements) == 0:
            raise Exception("No clickable elements found with text 'Übersicht'")
        
        # click on center of the first element
        element = elements[0]
        self.adb_client.click_on_element(element)
        time.sleep(3)

    def _open_widget_by_name(self, name: str):
        if not self.is_overview():
            print("Übersicht not found, restarting...")
            return False

        widget = self.adb_client.find_element_by_scroll(name)

        if widget == False:
            print(f"Widget '{name}' not found, restarting...")
            return False

        bounds = self.adb_client.find_center_of_element(widget)

        self.adb_client.click(580, bounds[1])

        time.sleep(8)






class VirtualAccount:
    @classmethod
    def list_from_json_file(cls, file_path: str):
        """
        Load a list of VirtualAccount objects from a JSON file.
        :param file_path: Path to the JSON file.
        :return: List of VirtualAccount objects.
        """

        with open(file_path, 'r') as file:
            data = json.load(file)
            return [cls(**item) for item in data]
    
    def __init__(self, name: str, balance: float):
        self.name = name
        self.balance = balance
