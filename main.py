import time
from datetime import datetime, timedelta, timezone
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from seleniumbase import Driver
import pandas as pd
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
import re
import json
import subprocess
import bs4

import random


def create_driver():
    """Create and return a maximized SeleniumBase Driver."""
    driver = Driver()
    driver.maximize_window()
    return driver


def extract_result_items_from_soup(page_soup):
    """Extract product item elements from a page soup.

    Returns:
        dict: {status: bool, data: list, error: str}
    """
    try:
        items = page_soup.select(
            'div.component-product-list div[class*=" product-item"]'
        )
        return {
            "status": True,
            "data": items,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": [],
            "error": str(exc),
        }


def extract_data_from_result_page_item(element):
    """Extract item data from a result page item element."""
    try:
        if element is None:
            return {
                "status": False,
                "data": {},
                "error": "Element is None",
            }

        ITEM_NAME_SELECTOR = "span.title-con"
        ITEM_URL_SELECTOR = 'a[class*="title-link"]'
        PRICE_SELECTOR = "div.price"

        item_name_element = element.select_one(ITEM_NAME_SELECTOR)
        item_url_element = element.select_one(ITEM_URL_SELECTOR)
        price_element = element.select_one(PRICE_SELECTOR)

        data = {
            "item_name": item_name_element.get_text(strip=True)
            if item_name_element
            else None,
            "item_url": item_url_element.get("href") if item_url_element else None,
            "price": price_element.get_text(strip=True) if price_element else None,
        }

        return {
            "status": True,
            "data": data,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {},
            "error": str(exc),
        }


def click_next_pagination_btn(driver):
    """Click the next pagination button if enabled."""
    try:
        wait = WebDriverWait(driver, 10)
        next_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button[class*="next-pagination-item next"]')
            )
        )

        disabled_attr = next_btn.get_attribute("disabled")
        btn_classes = (next_btn.get_attribute("class") or "").lower()

        if disabled_attr or "disabled" in btn_classes:
            return {
                "status": False,
                "error": "btn disabled",
            }

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            next_btn,
        )
        next_btn.click()
        time.sleep(2)
        return {
            "status": True,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "error": str(exc),
        }


def extract_categories(driver):
    """Extract product categories from a page using the Selenium driver."""
    try:
        wait = WebDriverWait(driver, 10)
        category_elements = wait.until(
            EC.presence_of_all_elements_located(
                (
                    By.CSS_SELECTOR,
                    'div[module-title="productGroups"] li[role="menuitem"]',
                )
            )
        )

        category_names = list(map(lambda el: el.text.strip(), category_elements))

        return {
            "status": True,
            "data": dict(zip(category_names, category_elements)),
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": [],
            "error": str(exc),
        }


url = "https://nbbsj.en.alibaba.com/productlist.html"
# driver = create_driver()
# driver.get(url)

soup = driver.get_page_source()
bs = bs4.BeautifulSoup(soup, "html.parser")

result = extract_item_soup(bs)

elemento = result.get("data")[1]
extract_data_from_result_page_item(elemento)

time.sleep(2)
click_next_pagination_btn(driver)
