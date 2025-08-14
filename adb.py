from dataclasses import dataclass
import shlex
import subprocess
import traceback
from ppadb.client import Client
from ppadb.device import Device
import time
import xml.etree.ElementTree as ET
import io
from PIL import Image

import pytesseract
pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files/Tesseract-OCR/tesseract.exe'

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

    def __init__(self, device: Device = None, adb_binary_path: str = "adb"):
        """
        Initialize the Adb class with the given device.
        If no device is provided, it will use the first available device.
        """

        if device is None:
            device = Client().devices()[0]

        self.device: Device = device
        self.adb_binary_path: str = adb_binary_path

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
        time.sleep(10)

    def _get_current_xml(self) -> ET.Element:
        """
        Return the root <hierarchy> element of the current UI-Automator dump.

        1. Host-side command
               adb -s <serial> exec-out uiautomator dump /dev/tty
           streams the XML directly to the PC - no temp file needed.

        2. If that fails (very old Android), we fall back to the
           original /sdcard/window_dump.xml method.
        """
        import subprocess, io

        try:
            # ── direct exec-out (fast & no SD-card writes) ─────────────
            raw: bytes = subprocess.check_output(
                [self.adb_binary_path, "-s", self.device.serial,
                 "exec-out", "uiautomator", "dump", "/dev/tty"],
                stderr=subprocess.STDOUT,
            )
            # uiautomator prints a status line AFTER the XML – discard it
            xml_start = raw.find(b"<?xml")
            xml_bytes = raw[xml_start:]
            xml_str = xml_bytes.decode("utf-8", errors="replace")

        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            print(traceback.format_exc())
            print("Failed to get current XML, falling back to legacy method")
            # ── fallback to legacy two-step method ─────────────────────
            self.device.shell("uiautomator dump /sdcard/window_dump.xml")
            # xml_str = self.device.shell("cat /sdcard/window_dump.xml")
            self.device.pull("/sdcard/window_dump.xml", "window_dump.xml")
            with open("window_dump.xml", "r", encoding="utf-8") as f:
                xml_str = f.read()

        tree = ET.parse(io.StringIO(xml_str))
        return tree.getroot()
    

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
    
    def screencap(self) -> Image.Image:
        """
        Return a Pillow Image of the current screen.

        Strategy:
          A) host-side   adb exec-out screencap -p   ← identical to CLI
          B) in-shell    screencap -p                ← CR/LF fix
          C) file hack   screencap to /sdcard + cat  ← last resort
        """

        serial = self.device.serial
        try:
            # A) exact same command that works in your cmd prompt
            raw = subprocess.check_output(
                shlex.split(f'"{self.adb_binary_path}" -s {serial} exec-out screencap -p'),
                stderr=subprocess.DEVNULL,   # suppress 'Killed by signal' noise
            )
            if raw.startswith(b"\x89PNG"):
                return Image.open(io.BytesIO(raw))
            print(raw[:100])
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(traceback.format_exc())
            raw = None  # fall through

        # B) shell pipe (works back to Android 4.x, needs CR/LF fix)
        def _run_bytes(cmd: str) -> bytes:
            try:
                return self.device.shell(cmd, decode=False)
            except TypeError:                       # old ppadb
                out = self.device.shell(cmd)
                return out.encode("latin1", "ignore") if isinstance(out, str) else out

        raw = _run_bytes("screencap -p")
        if raw and raw.startswith(b"\x89PNG"):
            raw = raw.replace(b"\r\n", b"\n")       # pre-Nougat fix
            try:
                return Image.open(io.BytesIO(raw))
            except Exception:
                pass

        raise Exception(
            "Failed to get screenshot. "
            "Try running 'adb kill-server' and 'adb start-server' first."
        )

    def screencap_text(self) -> list[BasicElement]:
        """
        Run Tesseract OCR on a fresh screenshot and return a list of
        BasicElement(text, x1, y1, x2, y2, element=None).

        Coordinates use the phone’s physical pixel grid, matching
        the values returned by UI-Automator.
        """
        img = self.screencap()                      # Pillow Image
        ocr = pytesseract.image_to_data(
            img, output_type=pytesseract.Output.DICT, lang="eng"
        )

        elements: list[BasicElement] = []
        n_boxes = len(ocr["text"])
        for i in range(n_boxes):
            txt = ocr["text"][i].strip()
            if not txt:                             # ignore empty tokens
                continue
            x, y, w, h = (
                ocr["left"][i],
                ocr["top"][i],
                ocr["width"][i],
                ocr["height"][i],
            )
            elements.append(BasicElement(txt, x, y, x + w, y + h, None))

        return elements

    def back_keyevent(self):
        """
        Press the back button on the device.
        This method uses the 'input keyevent' command to simulate a back button press.
        """

        self.device.shell("input keyevent KEYCODE_BACK")
        time.sleep(3)

    def enter_keyevent(self):
        """
        Press the enter button on the device.
        This method uses the 'input keyevent' command to simulate an enter button press.
        """

        self.device.shell("input keyevent KEYCODE_ENTER")
        time.sleep(3)
    
    def get_elements_by_text(self, text: str, from_screencap = False) -> list[BasicElement]:
        """
        Find an element by its text attribute in the current XML hierarchy.
        This method searches for the element in the XML hierarchy and returns it if found.
        If the element is not found, it returns False.
        """

        if from_screencap:
            elements = self.screencap_text()
            return [e for e in elements if text.lower() in e.text.lower()]
        else:
            elements, _ = self.get_list_of_elements()
            return [e for e in elements if text in e.text]
    
    def find_element_by_scroll(self, text: str, down: bool = True, max_tries: int = 5, from_screencap = False) -> BasicElement:
        """
        Find an element by its text attribute in the current XML hierarchy.
        This method scrolls the screen in the specified direction (down or up) to find the element.
        If the element is not found after the specified number of tries, it returns False.
        """

        for i in range(max_tries):
            if from_screencap:
                elements = self.screencap_text()
                for element in elements:
                    if text.lower() in element.text.lower():
                        return element
            else:
                el = self.get_elements_by_text(text)
                if el:
                    for element in el:
                        if element.text == text:
                            return element
            
            print(f"Element '{text}' not found, scrolling {'down' if down else 'up'}...")
            if down:
                self.device.shell("input swipe 500 1000 500 500")
            else:
                self.device.shell("input swipe 500 500 500 1000")
            time.sleep(5)
        
        return False
    
    def get_center_of_element(self, element: BasicElement) -> tuple[int, int]:
        """
        Find the center of the given element.
        This method calculates the center coordinates of the element based on its bounds.
        """
        
        return int(round((element.x1+element.x2)/2)), int(round((element.y1+element.y2)/2))
    
    def click(self, x: int, y: int):
        """
        Click on the given coordinates.
        This method simulates a click on the specified coordinates using the 'input tap' command.
        """

        print(f"Clicking on coordinates ({x}, {y})")
        self.device.shell(f"input tap {x} {y}")
        time.sleep(2)

    def click_element(self, element: BasicElement):
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