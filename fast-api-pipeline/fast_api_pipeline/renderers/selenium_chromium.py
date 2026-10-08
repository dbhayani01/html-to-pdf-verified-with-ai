"""Selenium with headless Chromium HTML-to-PDF renderer."""

import base64
import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def render(html_path: Path, pdf_path: Path) -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    chrome_binary = os.environ.get("CHROME_BINARY")
    if chrome_binary:
        options.binary_location = chrome_binary

    driver_path = os.environ.get("CHROMEDRIVER_PATH")
    service = Service(driver_path or ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(html_path.resolve().as_uri())
        time.sleep(3)
        pdf_data = driver.execute_cdp_cmd(
            "Page.printToPDF",
            {"printBackground": True, "orientation": "portrait", "scale": 1.0},
        )
        pdf_path.write_bytes(base64.b64decode(pdf_data["data"]))
    finally:
        driver.quit()
