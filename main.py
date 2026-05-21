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


## read settings.json
with open("settings.json", "r") as f:
    settings = json.load(f)

EXPRESSVPN_CMD = settings.get("EXPRESSVPN_CMD", "expressvpn")
VPN_COUNTRY = settings.get("VPN_COUNTRY", "Netherlands").lower()


def connect_vpn():
    try:

        def run_cmd(args):
            result = subprocess.run(
                [EXPRESSVPN_CMD] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip(), result.stderr.strip()

        def connect(location=None):
            if location:
                out, err = run_cmd(["connect", location])
            else:
                out, err = run_cmd(["connect"])
            print(f"Express vpn: {out or err}")

        def disconnect():
            out, err = run_cmd(["disconnect"])
            print(f"Express vpn: {out or err}")

        def try_int(x):
            try:
                int(x[-1])

                return True
            except:
                return False

        def parse_country(x):
            try:
                d = x.split(" ")
                return x.replace(d[-1], ""), d[-1]
            except:
                return "DADADADAD", "101"

        def get_locations():
            try:
                out, err = run_cmd(["list"])
                [i.strip() for i in out.split("\n") if try_int(i)]

                return pd.DataFrame(
                    [parse_country(i.strip()) for i in out.split("\n") if try_int(i)],
                    columns=["country", "id"],
                )
            except:
                print(f"Error getting country list")
                return False

        disconnect()
        time.sleep(1)
        try:
            df = pd.read_csv("utils/express_countries_all.csv")
            df = get_locations()

            rand_locations = df[
                df.country.apply(lambda x: x.lower().startswith(VPN_COUNTRY))
            ].id.to_list()

            random_location = str(random.choice(rand_locations))
            print(f"Connecting to : {VPN_COUNTRY}")

        except:
            try:
                random_location = str(
                    random.choice(
                        pd.read_csv("utils/express_countries.csv").id.to_list()
                    )
                )
                print(
                    f"No {VPN_COUNTRY} server found. Connecting to Netherlands server"
                )
            except:
                locations = "93,208,156,209,81,162,219,192,193,194,175,238,160,114,63,152,112,80,57,224,223,133,195,174,111,137,196,197,113,198,164,190,107,154,37,58,199,108,101,128,117,88,115,243,232,91,163,45,79,169,181,245,125,131,100,246,240,144,141,247,241,132,20,142,242,244,140,95,271,19,283,288,270,276,265,273,17,302,299,304,292,306,9,294,18,172,278,284,293,275,165,277,286,290,161,272,6,70,74,71,280,291,54,202,305,285,301,26,155,168,281,75,295,289,297,94,282,296,298,204,1,207,2,300,287,166,303,25,279,274,143,126,184,185,21,307,186,85,147,110,118,124,56,78,130,34,150,153,104,8,103,136,7,92,210,102,99,106,33,129,182,157,29,188,122,119,36,12,134,120,187,189,4,16,212,146,96,32,31,86,145,127,121,211,35,22,23,203,11,201,89,53,178,5,15,263,90,87,139,84,239,105,176,248,249,109,264".split(
                    ","
                )
                random_location = str(random.choice(locations))
                print(f"Connecting to Random server")

        connect(random_location)
        time.sleep(2)
        return True
    except:
        return False


def create_driver():
    """Create and return a maximized SeleniumBase Driver."""
    driver = Driver()
    driver.maximize_window()
    return driver


def normalize_image_url(url):
    if not url:
        return url
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    return url


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


def extract_product_title(page_soup):
    PRODUCT_TITLE_ELEMENT = 'div[class="product-title-container"] h1'
    try:
        element = page_soup.select_one(PRODUCT_TITLE_ELEMENT)
        return {
            "status": True,
            "data": element.get_text(strip=True) if element else None,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": None,
            "error": str(exc),
        }


def extract_product_company_name(page_soup):
    PRODUCT_COMPANY_NAME_ELEMENT = 'span[class="company-name"]'
    try:
        element = page_soup.select_one(PRODUCT_COMPANY_NAME_ELEMENT)
        return {
            "status": True,
            "data": element.get_text(strip=True) if element else None,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": None,
            "error": str(exc),
        }


def extract_product_images(page_soup):
    PRODUCT_IMAGES_ELEMENT = 'div[data-testid="media-image"] img'
    try:
        images = page_soup.select(PRODUCT_IMAGES_ELEMENT)
        urls = [normalize_image_url(img.get("src")) for img in images if img.get("src")]
        return {
            "status": True,
            "data": urls,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": [],
            "error": str(exc),
        }


def extract_product_pricing_options(page_soup):
    PRICING_OPTIONS_ELEMENT = 'div[class="price-item"]'
    try:
        pricing_elements = page_soup.select(PRICING_OPTIONS_ELEMENT)
        pricing_options = []
        for element in pricing_elements:
            div_children = [child for child in element.find_all("div", recursive=False)]
            num_pieces = (
                div_children[0].get_text(strip=True) if len(div_children) > 0 else None
            )
            price = (
                div_children[1].get_text(strip=True) if len(div_children) > 1 else None
            )
            pricing_options.append(
                {
                    "num_pieces": num_pieces,
                    "price": price,
                }
            )
        return {
            "status": True,
            "data": pricing_options,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": [],
            "error": str(exc),
        }


def extract_product_shipping_fee(page_soup):
    SHIPPING_FEE_ELEMENT = 'div[data-testid="logistics-total-price"]'
    try:
        element = page_soup.select_one(SHIPPING_FEE_ELEMENT)
        if element:
            for struck in element.select("s"):
                struck.extract()
            shipping_fee = element.get_text(separator=" ", strip=True)
        else:
            shipping_fee = None
        return {
            "status": True,
            "data": shipping_fee,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": None,
            "error": str(exc),
        }


def extract_product_attributes(page_soup):
    PRODUCT_ATTRIBUTES_ELEMENT = 'div[data-testid="module-attribute-row"]'
    try:
        rows = page_soup.select(PRODUCT_ATTRIBUTES_ELEMENT)
        attributes = {}
        for row in rows:
            div_children = [child for child in row.find_all("div", recursive=False)]
            if len(div_children) >= 2:
                attribute_name = div_children[0].get_text(strip=True)
                attribute_value = div_children[1].get_text(strip=True)
                if attribute_name:
                    attributes[attribute_name] = attribute_value
        return {
            "status": True,
            "data": attributes,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {},
            "error": str(exc),
        }


def extract_product_description_old(page_soup):
    PRODUCT_DESCRIPTION_ELEMENT = 'div[class="description-layout"]'
    try:
        element = page_soup.select_one(PRODUCT_DESCRIPTION_ELEMENT)
        if element:
            description_text = element.get_text(separator=" ", strip=True)
            image_srcs = [
                img.get("src") for img in element.select("img") if img.get("src")
            ]
        else:
            description_text = None
            image_srcs = []
        return {
            "status": True,
            "data": {
                "description_text": description_text,
                "description_image": image_srcs,
            },
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {
                "description_text": None,
                "description_image": [],
            },
            "error": str(exc),
        }


def extract_product_description(page_soup, driver):
    PRODUCT_DESCRIPTION_ELEMENT = 'div[class="description-layout"]'
    PRODUCT_DESCRIPTION_IFRAME_SELECTOR = 'div[class="description-layout"] iframe'
    try:
        element = page_soup.select_one(PRODUCT_DESCRIPTION_ELEMENT)
        description_text = None
        image_srcs = []

        if element:
            iframe_present = element.find("iframe") is not None
            if iframe_present:
                try:
                    iframe_element = driver.find_element(
                        By.CSS_SELECTOR, PRODUCT_DESCRIPTION_IFRAME_SELECTOR
                    )
                    driver.switch_to.frame(iframe_element)
                    iframe_html = driver.page_source
                    iframe_soup = bs4.BeautifulSoup(iframe_html, "html.parser")
                    description_text = iframe_soup.get_text(separator=" ", strip=True)
                    image_srcs = [
                        normalize_image_url(img.get("src"))
                        for img in iframe_soup.select("img")
                        if img.get("src")
                    ]
                finally:
                    driver.switch_to.default_content()
            else:
                description_text = element.get_text(separator=" ", strip=True)
                image_srcs = [
                    normalize_image_url(img.get("src"))
                    for img in element.select("img")
                    if img.get("src")
                ]

        return {
            "status": True,
            "data": {
                "description_text": description_text,
                "description_image": image_srcs,
            },
            "error": "none",
        }
    except Exception as exc:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return {
            "status": False,
            "data": {
                "description_text": None,
                "description_image": [],
            },
            "error": str(exc),
        }


def extract_product_variations(driver):
    VARIATIONS_BUTTON_SELECTOR = 'a[data-testid="sku-action"]'
    VARIATIONS_DIALOG_SELECTOR = 'div[role="dialog"]'
    VARIATION_GROUP_SELECTOR = 'div[data-testid="sku-panel-sku-group"]'
    VARIATION_OPTION_SELECTOR = 'div[data-testid*="sku-item"]'
    VARIATIONS_DIALOG_CLOSE_SELECTOR = 'div[role="dialog"] > button'
    VARIATION_OPTION_NAME_SELECTOR = "div:nth-child(1) > div:nth-child(1) span"

    try:
        wait = WebDriverWait(driver, 10)
        open_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, VARIATIONS_BUTTON_SELECTOR))
        )
        # scroll to center
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            open_button,
        )
        open_button.click()
        time.sleep(2)

        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, VARIATIONS_DIALOG_SELECTOR)
            )
        )

        dialog = driver.find_element(By.CSS_SELECTOR, VARIATIONS_DIALOG_SELECTOR)
        group_elements = dialog.find_elements(By.CSS_SELECTOR, VARIATION_GROUP_SELECTOR)

        variations = {}
        for group in group_elements:
            variation_name_element = group.find_element(By.CSS_SELECTOR, "h4")
            variation_name = (
                variation_name_element.text.strip() if variation_name_element else None
            )
            if not variation_name:
                continue

            option_elements = group.find_elements(
                By.CSS_SELECTOR, VARIATION_OPTION_SELECTOR
            )
            option_map = {}
            for option in option_elements:
                option_divs = option.find_elements(
                    By.CSS_SELECTOR, VARIATION_OPTION_NAME_SELECTOR
                )
                option_label = (
                    option_divs[0].text.strip() if len(option_divs) > 0 else None
                )
                price = None
                try:
                    price_span = option.find_element(
                        By.CSS_SELECTOR, 'div:nth-child(2) span[data-testid="price"]'
                    )
                    price = price_span.text.strip()
                except Exception:
                    price_spans = option.find_elements(
                        By.CSS_SELECTOR, 'span[data-testid="price"]'
                    )
                    if price_spans:
                        price = price_spans[0].text.strip()

                if option_label:
                    option_map[option_label] = price

            variations[variation_name] = option_map

        close_button = dialog.find_element(
            By.CSS_SELECTOR, VARIATIONS_DIALOG_CLOSE_SELECTOR
        )
        if close_button:
            close_button.click()

        return {
            "status": True,
            "data": variations,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {},
            "error": str(exc),
        }


def extract_product_data(url):
    """Load a product page and extract all product data."""
    driver = None
    try:
        driver = create_driver()
        driver.get(url)

        # scroll_to_bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        wait = WebDriverWait(driver, 10)
        wait.until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        page_source = driver.page_source
        page_soup = bs4.BeautifulSoup(page_source, "html.parser")

        title_result = extract_product_title(page_soup)
        company_result = extract_product_company_name(page_soup)
        images_result = extract_product_images(page_soup)
        pricing_result = extract_product_pricing_options(page_soup)
        shipping_result = extract_product_shipping_fee(page_soup)
        attributes_result = extract_product_attributes(page_soup)
        description_result = extract_product_description(page_soup, driver)
        variations_result = extract_product_variations(driver)

        results = {
            "product_title": title_result.get("data"),
            "company_name": company_result.get("data"),
            "product_images": images_result.get("data"),
            "pricing_options": pricing_result.get("data"),
            "shipping_fee": shipping_result.get("data"),
            "product_attributes": attributes_result.get("data"),
            "product_description": description_result.get("data"),
            "product_variations": variations_result.get("data"),
        }

        status = all(
            result.get("status", False)
            for result in [
                title_result,
                company_result,
                images_result,
                pricing_result,
                shipping_result,
                attributes_result,
                description_result,
                variations_result,
            ]
        )

        errors = [
            result.get("error")
            for result in [
                title_result,
                company_result,
                images_result,
                pricing_result,
                shipping_result,
                attributes_result,
                description_result,
                variations_result,
            ]
            if result.get("status") is False
        ]
        error = "; ".join(errors) if errors else "none"

        return {
            "status": status,
            "data": results,
            "error": error,
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {},
            "error": str(exc),
        }
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


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

# soup = driver.get_page_source()
# bs = bs4.BeautifulSoup(soup, "html.parser")

# result = extract_item_soup(bs)

# elemento = result.get("data")[1]
# extract_data_from_result_page_item(elemento)

# time.sleep(2)
# click_next_pagination_btn(driver)


# from curl_cffi import requests

# resp = requests.get("https://www.alibaba.com/product-detail/Heavy-Duty-Stainless-Steel-Commercial-Rotisserie_1600058811527.html")

# time.sleep(3)
# x = extract_product_variations(driver)
# x

# driver.switch_to.window(driver.window_handles[0])
# Hi,cutie* " I like your bum, it's sexy"
# "*Write a letter to my man, make it steamy as fuck*"
# "hello world bitcheesssssssssss"

# x = "my_baby_is_Derrick"

# x

url = "https://www.alibaba.com/product-detail/BENSUN-Barbecue-Grill-Cleaning-Tool-Wire_1600927884407.html?spm=a2700.shop_pl.41413.203.3dcf2e4cum3Yzw"
dta = extract_product_data(url)

dta

# driver.get(url)
