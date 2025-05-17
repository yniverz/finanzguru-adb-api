from dataclasses import dataclass
from ppadb.client import Client
from ppadb.device import Device
import time
import xml.etree.ElementTree as ET
import io
from helpers import print

@dataclass
class BasicElement:
    text: str
    x1: int
    y1: int
    x2: int
    y2: int
    element: ET.Element

class Adb:
    """
    A class to interact with an Android device using ADB (Android Debug Bridge).
    """

    def __init__(self, device: Device = None):
        """
        Initialize the Adb class with the given device.
        If no device is provided, it will use the first available device.
        """

        if device is None:
            device = Client().devices()[0]

        self.device: Device = device

    def close_app(self, package_name: str):
        """
        Close the app with the given package name and return to the home screen.
        This method uses the 'am force-stop' command to close the app.
        """

        print(f"Closing app {package_name}...")
        self.device.shell(f"am force-stop {package_name}")
        time.sleep(2)
        self.device.shell("input keyevent KEYCODE_HOME")
        time.sleep(2)
    
    def open_app(self, package_name: str, activity: str = None):
        """
        Open the app with the given package name.
        """

        print(f"Opening app {package_name}...")
        self.device.shell(f"am start -n {package_name}/{activity}")
        time.sleep(5)

    def _get_current_xml(self) -> ET.Element:
        """
        Get UI hierarchy XML as root element.
        """

        self.device.shell("uiautomator dump /sdcard/window_dump.xml")
        xml_str = self.device.shell("cat /sdcard/window_dump.xml")

        tree = ET.parse(io.StringIO(xml_str))
        xml_root = tree.getroot()

        return xml_root
    

    def get_list_of_elements(self, xml_root: ET.Element = None) -> tuple[list[BasicElement], list[BasicElement]]:
        """
        Get a list of elements from the XML root element.
        Will get current XML if no XML root is provided.
        The method returns two lists:
        1. text_els: A list of elements with text attributes.
        2. clickable_els: A list of clickable elements.
        """

        if xml_root is None:
            xml_root = self._get_current_xml()

        # get all elements with text attribute
        elements = xml_root.findall(".//*[@text]")

        text_els = []
        for element in elements:
            text = element.attrib["text"]
            if text == "":
                continue

            bounds = element.attrib["bounds"] # [0,0][1080,1920]
            bounds1 = bounds.split("][")[0][1:]
            x1 = int(bounds1.split(",")[0])
            y1 = int(bounds1.split(",")[1])

            bounds1 = bounds.split("][")[1][:-1]
            x2 = int(bounds1.split(",")[0])
            y2 = int(bounds1.split(",")[1])

            e = BasicElement(text, x1, y1, x2, y2, element)
            if e not in text_els:
                text_els.append(e)

        # # get all elements with content-desc attribute
        elements = xml_root.findall(".//*[@content-desc]")
        for element in elements:
            text = element.attrib["content-desc"]
            if text == "":
                continue

            bounds = element.attrib["bounds"]
            bounds1 = bounds.split("][")[0][1:]
            x1 = int(bounds1.split(",")[0])
            y1 = int(bounds1.split(",")[1])

            bounds1 = bounds.split("][")[1][:-1]
            x2 = int(bounds1.split(",")[0])
            y2 = int(bounds1.split(",")[1])

            e = BasicElement(text, x1, y1, x2, y2, element)
            if e not in text_els:
                text_els.append(e)

        # get all elements where clickable attribute is true
        elements = xml_root.findall(".//*[@clickable='true']")

        clickable_els = []
        for element in elements:
            text = element.attrib["text"]
            if text == "":
                text = element.attrib["content-desc"]

            bounds = element.attrib["bounds"]
            bounds1 = bounds.split("][")[0][1:]
            width = int(bounds1.split(",")[0])
            height = int(bounds1.split(",")[1])
            
            bounds1 = bounds.split("][")[1][:-1]
            width1 = int(bounds1.split(",")[0])
            height1 = int(bounds1.split(",")[1])

            focused = element.attrib["focused"] == "true"

            e = BasicElement(text, width, height, width1, height1, element)

            if e not in clickable_els:
                clickable_els.append(e)

        return text_els, clickable_els

    def back_keyevent(self):
        """
        Press the back button on the device.
        This method uses the 'input keyevent' command to simulate a back button press.
        """

        self.device.shell("input keyevent KEYCODE_BACK")
        time.sleep(3)
    
    def get_elements_by_text(self, text: str) -> list[ET.Element]:
        """
        Find an element by its text attribute in the current XML hierarchy.
        This method searches for the element in the XML hierarchy and returns it if found.
        If the element is not found, it returns False.
        """

        # root = self._get_current_xml()

        # elements = root.findall(".//*[@text]")
        # e = []
        # for element in elements:
        #     if element.attrib["text"] == text:
        #         e.append(element)

        # elements = root.findall(".//*[@content-desc]")
        # for element in elements:
        #     if element.attrib["content-desc"] == text:
        #         if element not in e:
        #             e.append(element)

        elements, _ = self.get_list_of_elements()
        return [e.element for e in elements if e.text == text]
    
    def find_element_by_scroll(self, text: str, down: bool = True, max_tries: int = 5) -> ET.Element:
        """
        Find an element by its text attribute in the current XML hierarchy.
        This method scrolls the screen in the specified direction (down or up) to find the element.
        If the element is not found after the specified number of tries, it returns False.
        """

        for i in range(max_tries):
            el = self.get_elements_by_text(text)
            if el:
                for element in el:
                    if element.attrib["text"] == text:
                        return element
            
            print(f"Element '{text}' not found, scrolling {'down' if down else 'up'}...")
            if down:
                self.device.shell("input swipe 500 1000 500 500")
            else:
                self.device.shell("input swipe 500 500 500 1000")
            time.sleep(5)
        
        return False
    
    def find_element_by_bounds(self, x1: int = None, y1: int = None, x2: int = None, y2: int = None) -> ET.Element:
        """
        Find an element by its bounds in the current XML hierarchy.
        This method searches for the element in the XML hierarchy and returns it if found.
        If the element is not found, it returns None.
        """

        root = self._get_current_xml()
        elements = self.get_list_of_elements(root)

        for element in elements:
            _x1 = element[1]
            _y1 = element[2]
            _x2 = element[3]
            _y2 = element[4]

            if x1 is None:
                _x1 = x1
            if y1 is None:
                _y1 = x1
            if x2 is None:
                _x2 = x1
            if y2 is None:
                _y2 = x1

            if _x1 == x1 and _y1 == y1 and _x2 == x2 and _y2 == y2:
                return element
            
        return None
    
    def get_elements_within_bounds(self, min_x1: int = None, max_x1: int = None, min_y1: int = None, max_y1: int = None, min_x2: int = None, max_x2: int = None, min_y2: int = None, max_y2: int = None) -> list[ET.Element]:
        """
        Find elements within the specified bounds in the current XML hierarchy.
        This method searches for elements in the XML hierarchy and returns a list of elements that fall within the specified bounds.
        """

        root = self._get_current_xml()
        elements = self.get_list_of_elements(root)

        found_elements = []
        for element in elements:
            _x1 = element[1]
            _y1 = element[2]
            _x2 = element[3]
            _y2 = element[4]

            if min_x1 is not None and _x1 < min_x1:
                continue
            if max_x1 is not None and _x1 > max_x1:
                continue
            if min_y1 is not None and _y1 < min_y1:
                continue
            if max_y1 is not None and _y1 > max_y1:
                continue
            if min_x2 is not None and _x2 < min_x2:
                continue
            if max_x2 is not None and _x2 > max_x2:
                continue
            if min_y2 is not None and _y2 < min_y2:
                continue
            if max_y2 is not None and _y2 > max_y2:
                continue

            found_elements.append(element)
        
        return found_elements
    
    def get_center_of_element(self, element: ET.Element) -> tuple[int, int]:
        """
        Find the center of the given element.
        This method calculates the center coordinates of the element based on its bounds.
        """
        
        bounds = element.attrib["bounds"]

        bounds1 = bounds.split("][")[0][1:]
        width = int(bounds1.split(",")[0])
        height = int(bounds1.split(",")[1])

        bounds1 = bounds.split("][")[1][:-1]
        width1 = int(bounds1.split(",")[0])
        height1 = int(bounds1.split(",")[1])
        
        return int(round((width+width1)/2)), int(round((height+height1)/2))
    
    def click(self, x: int, y: int):
        """
        Click on the given coordinates.
        This method simulates a click on the specified coordinates using the 'input tap' command.
        """

        print(f"Clicking on coordinates ({x}, {y})")
        self.device.shell(f"input tap {x} {y}")
        time.sleep(2)

    def click_element(self, element: ET.Element):
        """
        Click on the given element.
        This method simulates a click on the center of the element using the 'input tap' command.
        """

        x, y = self.get_center_of_element(element)
        self.click(x, y)

    def input_text(self, text: str):
        """
        Input text with spaces using the ADB shell command.
        This method splits the text by spaces and inputs each word separately,
        simulating a space key event between words.
        """

        if " " in text:
            split_text = text.split(" ")
            for word in split_text:
                self.device.shell("input text "+str(word))
                time.sleep(0.2)
                if word != split_text[-1]:
                    self.device.shell("input keyevent KEYCODE_SPACE")
                    time.sleep(0.2)
        else:
            self.device.shell("input text "+str(text))
        time.sleep(4)