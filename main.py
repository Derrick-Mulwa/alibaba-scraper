import time
from datetime import datetime, timedelta, timezone
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


from urllib.parse import urlparse

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
NUMBER_OF_THREADS = int(settings.get("NUMBER_OF_THREADS", 1))
VPN_RECONNECT_INTERVAL = int(
    settings.get("VPN_RECONNECT_INTERVAL", 20)
)  # Reconnect every N items

# VPN continent rotation list for handling shipping region errors
VPN_CONTINENTS = [
    "Australia",
    "UK",
    "Canada",
    "Indonesia",
    "Kenya",
    "Colombia",
    "France",
]

# Global counters for VPN reconnection
items_processed_counter = 0
vpn_counter_lock = threading.Lock()


def connect_vpn(country=VPN_COUNTRY):
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
                print("Error getting country list")
                return False

        disconnect()
        time.sleep(1)
        try:
            df = pd.read_csv("utils/express_countries_all.csv")
            df = get_locations()

            rand_locations = df[
                df.country.apply(lambda x: x.lower().startswith(country.lower()))
            ].id.to_list()

            random_location = str(random.choice(rand_locations))
            print(f"Connecting to : {country}")

        except:
            try:
                random_location = str(
                    random.choice(
                        pd.read_csv("utils/express_countries.csv").id.to_list()
                    )
                )
                print(f"No {country} server found. Connecting to Netherlands server")
            except:
                locations = "93,208,156,209,81,162,219,192,193,194,175,238,160,114,63,152,112,80,57,224,223,133,195,174,111,137,196,197,113,198,164,190,107,154,37,58,199,108,101,128,117,88,115,243,232,91,163,45,79,169,181,245,125,131,100,246,240,144,141,247,241,132,20,142,242,244,140,95,271,19,283,288,270,276,265,273,17,302,299,304,292,306,9,294,18,172,278,284,293,275,165,277,286,290,161,272,6,70,74,71,280,291,54,202,305,285,301,26,155,168,281,75,295,289,297,94,282,296,298,204,1,207,2,300,287,166,303,25,279,274,143,126,184,185,21,307,186,85,147,110,118,124,56,78,130,34,150,153,104,8,103,136,7,92,210,102,99,106,33,129,182,157,29,188,122,119,36,12,134,120,187,189,4,16,212,146,96,32,31,86,145,127,121,211,35,22,23,203,11,201,89,53,178,5,15,263,90,87,139,84,239,105,176,248,249,109,264".split(
                    ","
                )
                random_location = str(random.choice(locations))
                print("Connecting to Random server")

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


def shipping_region_error(page_soup):
    PRODUCT_TITLE_ELEMENT = 'div[class="unsafe-title"]'
    try:
        element = page_soup.select_one(PRODUCT_TITLE_ELEMENT)
        if element.text.lower().startswith(
            "sorry, this product  can't  be shipped to your region"
        ):
            return {
                "status": True,
                "data": element.get_text(strip=True) if element else None,
                "error": "Shipping region error",
            }
        else:
            return {
                "status": False,
                "data": None,
                "error": "none",
            }
    except Exception as exc:
        return {
            "status": False,
            "data": None,
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
    PRODUCT_COMPANY_NAME_ELEMENT = (
        'div[data-module-name="module_unifed_company_card"] a[class*="id-underline"]'
    )
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


def extract_product_video(page_soup):
    PRODUCT_VIDEOS_ELEMENT = 'div[class="detail-video-container"] video'
    try:
        videos = page_soup.select(PRODUCT_VIDEOS_ELEMENT)
        urls = [
            normalize_image_url(video.get("src"))
            for video in videos
            if video.get("src")
        ]
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
    PRICING_OPTION_ELEMENT = 'div[data-testid="ladder-price"]'

    SHILLING_ELEMENT = 'span[class*="id-font-bold"]'
    CENTS_ELEMENT = 'span[class*="id-font-semibold"]'

    try:
        option_element = page_soup.select_one(PRICING_OPTION_ELEMENT)
        if option_element:
            pricing_elements = option_element.select(PRICING_OPTIONS_ELEMENT)
        else:
            pricing_elements = page_soup.select(PRICING_OPTIONS_ELEMENT)

        pricing_options = []
        for element in pricing_elements:
            div_children = [child for child in element.find_all("div", recursive=False)]

            styled_price_element = (
                div_children[0].select(SHILLING_ELEMENT)
                if len(div_children) > 0
                else []
            )
            if styled_price_element:
                shillings = (
                    div_children[0].select(SHILLING_ELEMENT)[0].get_text(strip=True)
                )
                cents = div_children[0].select(CENTS_ELEMENT)[-1].get_text(strip=True)
                price = f"${shillings}.{cents}"
            else:
                price = (
                    div_children[0].get_text(strip=True)
                    if len(div_children) > 0
                    else None
                )
            num_pieces = (
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
    PRODUCT_DESCRIPTION_ELEMENT2 = 'div[class="module_structure_description"]'
    PRODUCT_DESCRIPTION_ELEMENT3 = 'div[class="module_description"]'

    PRODUCT_DESCRIPTION_IFRAME_SELECTOR = 'div[class="description-layout"] iframe'
    try:
        element = page_soup.select_one(PRODUCT_DESCRIPTION_ELEMENT)
        if not element:
            element = page_soup.select_one(PRODUCT_DESCRIPTION_ELEMENT2)
            PRODUCT_DESCRIPTION_IFRAME_SELECTOR = (
                f"{PRODUCT_DESCRIPTION_ELEMENT2} iframe"
            )
        if not element:
            element = page_soup.select_one(PRODUCT_DESCRIPTION_ELEMENT3)
            PRODUCT_DESCRIPTION_IFRAME_SELECTOR = (
                f"{PRODUCT_DESCRIPTION_ELEMENT3} iframe"
            )
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
                    description_text = iframe_soup.get_text(separator="\n", strip=True)
                    image_srcs = [
                        normalize_image_url(img.get("src"))
                        for img in iframe_soup.select("img")
                        if img.get("src")
                    ]
                finally:
                    driver.switch_to.default_content()
            else:
                description_text = element.get_text(separator="\n", strip=True)
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


def get_faq_content(driver):
    try:
        status = False
        error = "FAQ not available"
        faq_data = None
        FAQ_HEADER_ELEMENT = 'div[module-title="detailProductNavigation"]'
        FAQ_HEADER_ELEMENT2 = 'div[data-testid="product-detail-title"]'

        FAQ_DESCRIPTION_IFRAME_SELECTOR = (
            'div[data-module-name="module_product_specification"] iframe'
        )
        FAQ_SECTION_ELEMENT = 'div[data-section-title="FAQ"]'

        try:
            iframe_element = driver.find_element(
                By.CSS_SELECTOR, FAQ_DESCRIPTION_IFRAME_SELECTOR
            )

            driver.switch_to.frame(iframe_element)
        except:
            pass
        iframe_html = driver.page_source

        iframe_soup = bs4.BeautifulSoup(iframe_html, "html.parser")
        faq_header_elements = iframe_soup.select(FAQ_HEADER_ELEMENT)
        if not faq_header_elements:
            faq_header_elements = iframe_soup.select(FAQ_HEADER_ELEMENT2)

        faq_index = (
            [i.get_text().lower() for i in faq_header_elements].index("faq")
            if "faq" in [i.get_text().lower() for i in faq_header_elements]
            else -1
        )

        if faq_index == -1:
            faq_index = (
                [i.get_text().lower() for i in faq_header_elements].index("faqs")
                if "faqs" in [i.get_text().lower() for i in faq_header_elements]
                else -1
            )

        if faq_index != -1:
            faq_content = faq_header_elements[faq_index].find_next_siblings("div")

            faq_data = "\n".join(
                [
                    faq_content_item.get_text(separator="\n", strip=True)
                    for faq_content_item in faq_content
                    if faq_content_item.get_text(separator="\n", strip=True)
                ]
            )

            status = True
            error = "none"
        else:
            faq_content = (
                iframe_soup.select(FAQ_SECTION_ELEMENT)[0]
                if iframe_soup.select(FAQ_SECTION_ELEMENT)
                else None
            )
            if faq_content:
                faq_data = faq_content.get_text(separator="\n", strip=True)
                status = True
                error = "none"

        return {
            "status": status,
            "data": faq_data,
            "error": error,
        }
    except Exception as exc:
        faq_data = None
        return {
            "status": False,
            "data": None,
            "error": f"FAQ Content Extraction Error: {str(exc)}",
        }
    finally:
        driver.switch_to.default_content()


def extract_customization_options(driver):
    CUSTOM_SECTION_ELEMENT = 'div[data-auto-exp="skuCustomizationChoices"]'
    OPTION_GROUP_SELECTOR = 'div[class="id-mb-2"]'
    OPTION_DATA_ELEMENT = (
        'div[class*="id-overflow-hidden id-overflow-ellipsis id-whitespace-nowrap"]'
    )
    try:
        wait = WebDriverWait(driver, 3)
        custom_section = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CUSTOM_SECTION_ELEMENT))
        )

        customization_options = {}
        option_groups = custom_section.find_elements(
            By.CSS_SELECTOR, OPTION_GROUP_SELECTOR
        )
        for group in option_groups:
            group_data = {}
            image_src = ""
            group_name = group.text.strip()
            if not group_name:
                continue

            # option_elements = all following sibling divs till one like option OPTION_GROUP_SELECTOR

            option_elements = group.find_elements(
                By.XPATH, "./following-sibling::div[1]"
            )

            option_element = option_elements[0]

            option_image_element = option_element.find_element(By.CSS_SELECTOR, "img")
            if option_image_element:
                image_src = option_image_element.get_attribute("src")

            group_data["image_url"] = image_src

            option_data_element = option_element.find_elements(
                By.CSS_SELECTOR, OPTION_DATA_ELEMENT
            )

            option_name = ""
            option_details = ""
            if option_data_element:
                option_name = (
                    option_data_element[0].text.strip() if option_data_element else None
                )

                if len(option_data_element) > 1:
                    option_details = (
                        option_data_element[1].text.strip()
                        if len(option_data_element) > 1
                        else None
                    )

            group_data["option_name"] = option_name
            group_data["option_details"] = option_details

            customization_options[group_name] = group_data
        return {
            "status": True,
            "data": customization_options,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {},
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
        wait = WebDriverWait(driver, 5)
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
            # print(f"Variation Name: {variation_name}")
            if not variation_name:
                continue

            option_elements = group.find_elements(
                By.CSS_SELECTOR, VARIATION_OPTION_SELECTOR
            )
            option_map = {}
            for i, option in enumerate(option_elements):
                option_divs = option.find_elements(
                    By.CSS_SELECTOR, VARIATION_OPTION_NAME_SELECTOR
                )
                option_label = (
                    option_divs[0].text.strip()
                    if len(option_divs) > 0
                    else f"option_{i + 1}"
                )
                price = None
                try:
                    image = option.find_element(By.TAG_NAME, "img")
                    image_url = image.get_attribute("src") if image else None
                except Exception:
                    image_url = None
                # print(f"Option Label: {option_label}, Image URL: {image_url}")
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
                    option_map[option_label] = {"price": price, "image_url": image_url}

            variations[variation_name] = option_map

        customization_result = extract_customization_options(driver)

        close_button = dialog.find_element(
            By.CSS_SELECTOR, VARIATIONS_DIALOG_CLOSE_SELECTOR
        )
        if close_button:
            close_button.click()

        time.sleep(1)
        return_data = {}
        return_data["variations"] = variations
        if customization_result.get("status"):
            return_data["customization_options"] = customization_result.get("data")

        return {
            "status": True,
            "data": return_data,
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {},
            "error": str(exc),
        }


def change_language_and_currency(driver, language="English", currency="USD"):
    try:
        SAVE_BUTTON_ELEMENT = 'div[class="tnh-button"]'
        wait = WebDriverWait(driver, 10)
        language_currency_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-tnhkey="Language"]'))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            language_currency_button,
        )
        language_currency_button.click()
        time.sleep(3)

        action_chains = ActionChains(driver)

        # Language.
        # Enter language directly
        action_chains.send_keys(language).perform()
        time.sleep(1)
        action_chains.send_keys(Keys.ENTER).perform()
        time.sleep(1)
        action_chains.send_keys(Keys.TAB).perform()
        time.sleep(1)
        action_chains.send_keys(currency).perform()
        time.sleep(1)
        action_chains.send_keys(Keys.ENTER).perform()
        time.sleep(1)

        # Save changes
        save_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SAVE_BUTTON_ELEMENT))
        )
        save_button.click()
        time.sleep(1)
        return {
            "status": True,
            "data": {},
            "error": "none",
        }
    except Exception as exc:
        return {
            "status": False,
            "data": {},
            "error": str(exc),
        }


def extract_product_data(url):
    """Load a product page and extract all product data with VPN rotation for shipping region errors."""
    driver = None
    original_vpn_country = VPN_COUNTRY
    vpn_was_changed = False

    try:
        driver = create_driver()
        driver.get(url)

        # scroll_to_bottom
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        wait = WebDriverWait(driver, 10)
        wait.until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        page_source = driver.page_source
        page_soup = bs4.BeautifulSoup(page_source, "html.parser")

        # Check for shipping region error
        shipping_region_result = shipping_region_error(page_soup)

        if shipping_region_result.get("status"):
            print(f"[SHIPPING_REGION_ERROR] Detected. Attempting VPN rotation...")
            vpn_was_changed = True

            # Try each continent in the rotation list
            for continent_vpn in VPN_CONTINENTS:
                print(f"[VPN_ROTATION] Trying continent: {continent_vpn}")

                # Change VPN to the continent
                vpn_success = connect_vpn(continent_vpn)
                if not vpn_success:
                    print(
                        f"[VPN_ROTATION] Failed to connect to {continent_vpn}, skipping..."
                    )
                    continue

                try:
                    driver.quit()
                except:
                    pass

                driver = create_driver()
                driver.get(url)
                time.sleep(1)

                # Change language and currency
                try:
                    change_language_and_currency(
                        driver, language="English", currency="USD"
                    )
                except Exception as e:
                    print(f"[VPN_ROTATION] Failed to change language/currency: {e}")

                # Reload the page
                driver.get(url)
                time.sleep(2)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                wait.until(
                    lambda d: (
                        d.execute_script("return document.readyState") == "complete"
                    )
                )

                page_source = driver.page_source
                page_soup = bs4.BeautifulSoup(page_source, "html.parser")

                # Check if we can extract the title successfully
                title_result = extract_product_title(page_soup)
                if title_result.get("status") and title_result.get("data"):
                    print(
                        f"[VPN_ROTATION] Success with {continent_vpn}! Product title extracted."
                    )
                    break
                else:
                    print(
                        f"[VPN_ROTATION] Failed with {continent_vpn}. Trying next continent..."
                    )
        else:
            # No shipping region error, proceed normally
            title_result = extract_product_title(page_soup)

        # Extract all data
        company_result = extract_product_company_name(page_soup)
        images_result = extract_product_images(page_soup)
        videos_result = extract_product_video(page_soup)
        pricing_result = extract_product_pricing_options(page_soup)
        shipping_result = extract_product_shipping_fee(page_soup)
        attributes_result = extract_product_attributes(page_soup)
        description_result = extract_product_description(page_soup, driver)

        variations_result = extract_product_variations(driver)

        faq_result = get_faq_content(driver)

        results = {
            "product_title": title_result.get("data"),
            "company_name": company_result.get("data"),
            "product_images": images_result.get("data"),
            "product_videos": videos_result.get("data"),
            "pricing_options": pricing_result.get("data"),
            "shipping_fee": shipping_result.get("data"),
            "product_attributes": attributes_result.get("data"),
            "product_description": description_result.get("data"),
            "product_variations_and_customization": variations_result.get("data"),
            "faq_content": faq_result.get("data"),
        }

        status = all(
            result.get("status", False)
            for result in [
                title_result,
                # company_result,
                images_result,
                pricing_result,
                # shipping_result,
                # attributes_result,
                # description_result,
                # variations_result,
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
        # Reconnect to original VPN (US) if it was changed
        if vpn_was_changed:
            try:
                print(
                    f"[VPN_ROTATION] Reconnecting to original VPN: {original_vpn_country.upper()}"
                )
                connect_vpn(original_vpn_country)
            except Exception as e:
                print(f"[VPN_ROTATION] Failed to reconnect to original VPN: {e}")

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


def get_page_soup(driver):
    """Return a BeautifulSoup object for the current browser page."""
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass
    return bs4.BeautifulSoup(driver.page_source, "html.parser")


def extract_company_data_by_categories(company_url):
    """Scrape product items for each category on a company listing page."""
    driver = None
    collected_data = {}

    try:
        print(f"Extracting company data by categories from: {company_url}")
        driver = create_driver()
        driver.get(company_url)
        time.sleep(2)

        categories_result = extract_categories(driver)
        if not categories_result.get("status"):
            return {
                "status": False,
                "data": {},
                "error": categories_result.get("error", "failed to extract categories"),
            }

        category_names = list(categories_result.get("data", {}).keys())
        if not category_names:
            return {
                "status": False,
                "data": {},
                "error": "no categories found",
            }

        for category_name in category_names:
            try:
                print(f"Extracting items for category: {category_name}")
                refreshed_categories = extract_categories(driver)
                if not refreshed_categories.get("status"):
                    raise RuntimeError(
                        refreshed_categories.get(
                            "error", "failed to refresh categories"
                        )
                    )

                category_element = refreshed_categories.get("data", {}).get(
                    category_name
                )
                if category_element is None:
                    collected_data[category_name] = {
                        "item_count": 0,
                        "items": [],
                        "error": "category element not found",
                    }
                    continue

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
                    category_element,
                )
                category_element.click()
                time.sleep(2)

                category_items = []
                while True:
                    page_soup = get_page_soup(driver)
                    items_result = extract_result_items_from_soup(page_soup)
                    if items_result.get("status"):
                        for item in items_result.get("data", []):
                            extracted_item = extract_data_from_result_page_item(item)
                            if extracted_item.get("status"):
                                category_items.append(extracted_item.get("data"))
                            else:
                                category_items.append(
                                    {"error": extracted_item.get("error")}
                                )

                    next_result = click_next_pagination_btn(driver)
                    if not next_result.get("status"):
                        break

                collected_data[category_name] = {
                    "item_count": len(category_items),
                    "items": category_items,
                }
                print(
                    f"Extracted {len(category_items)} items for category: {category_name}"
                )
            except Exception as exc:
                collected_data[category_name] = {
                    "item_count": 0,
                    "items": [],
                    "error": str(exc),
                }
                print(
                    f"Failed to extract items for category: {category_name}. Error: {exc}"
                )

            try:
                driver.get(company_url)
                time.sleep(2)
            except Exception:
                pass

        return {
            "status": True,
            "data": collected_data,
            "error": "none",
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


def _safe_name(value, fallback="item"):
    """Create a filesystem-safe name from a string."""
    if not value:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._-")
    return cleaned[:80] or fallback


def load_company_urls():
    """Load company URLs from companies.txt."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    companies_path = os.path.join(base_dir, "companies.txt")
    if not os.path.exists(companies_path):
        return []

    urls = []
    with open(companies_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            for fragment in re.split(r"[\n,]+", line):
                candidate = fragment.strip().strip("\"'")
                if candidate.startswith(("http://", "https://")):
                    urls.append(candidate)

    return list(dict.fromkeys(urls))


def _company_slug_from_url(company_url):
    """Create a readable folder name from a company URL."""
    if not company_url:
        return "company"

    parsed = urlparse(company_url)
    hostname = (parsed.hostname or "").lower()
    if hostname:
        host_parts = [
            part for part in hostname.split(".") if part and part not in {"www", "en"}
        ]
        if host_parts:
            return _safe_name(host_parts[0], "company")

    path_parts = [
        part
        for part in parsed.path.split("/")
        if part and part not in {"productlist.html", "productlist"}
    ]
    if path_parts:
        return _safe_name(path_parts[0], "company")

    return "company"


def _append_log_entry(log_path, lock, status, item_name, item_url, error):
    """Append a structured line to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (
        f"{timestamp} | {status} | {item_name or 'N/A'} | {item_url or 'N/A'} | "
        f"{error or 'none'}\n"
    )
    with lock:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(line)


def _process_category_item(item_payload, category_name, output_dir, log_path, lock):
    """Extract a single product item and persist its data."""
    global items_processed_counter

    item_name = None
    item_url = None

    if isinstance(item_payload, dict):
        item_name = item_payload.get("item_name")
        item_url = item_payload.get("item_url")

    try:
        if not item_url:
            raise ValueError("missing item url")

        print(f"Extracting data for item: {item_name or item_url}")
        extraction_result = extract_product_data(item_url)
        if not extraction_result.get("status"):
            raise RuntimeError(extraction_result.get("error", "extraction failed"))

        category_dir = os.path.join(output_dir, _safe_name(category_name, "category"))
        os.makedirs(category_dir, exist_ok=True)

        file_name = f"{_safe_name(item_name or item_url, 'item')}.json"
        output_path = os.path.join(category_dir, file_name)
        payload = {
            "category": category_name,
            "item": item_payload,
            "extracted_data": extraction_result.get("data", {}),
            "status": extraction_result.get("status"),
            "error": extraction_result.get("error"),
        }
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        # Increment counter and check if VPN reconnection is needed
        with vpn_counter_lock:
            items_processed_counter += 1
            current_count = items_processed_counter

            if current_count % VPN_RECONNECT_INTERVAL == 0:
                print(f"\n[VPN] Processed {current_count} items. Reconnecting VPN...")
                try:
                    connect_vpn(VPN_COUNTRY)
                    print(f"[VPN] Reconnection completed at item {current_count}")
                except Exception as vpn_error:
                    print(f"[VPN] Reconnection error: {vpn_error}")

        _append_log_entry(log_path, lock, "success", item_name, item_url, "none")
        print(f"Data extracted successfully for item: {item_name or item_url}")
        return {
            "status": "success",
            "category": category_name,
            "item_name": item_name,
            "item_url": item_url,
            "file": output_path,
        }
    except Exception as exc:
        _append_log_entry(log_path, lock, "fail", item_name, item_url, str(exc))
        print(f"Failed to extract data for item: {item_name or item_url}")
        return {
            "status": "fail",
            "category": category_name,
            "item_name": item_name,
            "item_url": item_url,
            "error": str(exc),
        }


def extract_company_items_data(extracted_company_data_by_categories, company_url=None):
    """Extract each item from category results using multiple threads."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    company_slug = _company_slug_from_url(company_url)
    output_dir = os.path.join(base_dir, "extracted_data", company_slug)
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "log.txt")
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="utf-8"):
            pass

    if (
        isinstance(extracted_company_data_by_categories, dict)
        and "data" in extracted_company_data_by_categories
    ):
        category_payload = extracted_company_data_by_categories.get("data", {})
    else:
        category_payload = extracted_company_data_by_categories or {}

    tasks = []
    for category_name, category_data in category_payload.items():
        items = []
        if isinstance(category_data, dict):
            items = category_data.get("items", [])
        elif isinstance(category_data, list):
            items = category_data

        for item_payload in items:
            if isinstance(item_payload, dict):
                tasks.append((category_name, item_payload))

    lock = threading.Lock()
    results = {"status": True, "data": {}, "error": "none"}

    if not tasks:
        return results

    with ThreadPoolExecutor(max_workers=NUMBER_OF_THREADS) as executor:
        futures = [
            executor.submit(
                _process_category_item,
                item_payload,
                category_name,
                output_dir,
                log_path,
                lock,
            )
            for category_name, item_payload in tasks
        ]

        for future in futures:
            item_result = future.result()
            category_name = item_result.get("category")
            if category_name not in results["data"]:
                results["data"][category_name] = {"success": [], "fail": []}
            results["data"][category_name][
                "success" if item_result.get("status") == "success" else "fail"
            ].append(item_result)

    return results


if __name__ == "__main__":
    company_urls = load_company_urls()
    if not company_urls:
        raise SystemExit("No company URLs found in companies.txt")

    connect_vpn()
    all_results = []
    for company_url in company_urls:
        print(f"Processing company: {company_url}")
        category_result = extract_company_data_by_categories(company_url)
        item_result = extract_company_items_data(
            category_result, company_url=company_url
        )
        all_results.append({"company_url": company_url, "result": item_result})

    print(json.dumps(all_results, indent=2, ensure_ascii=False))


# connect_vpn()
# item_url = "https://www.alibaba.com/product-detail/High-Quality-Adult-Electric-Scooter-Fast_1600885974020.html"
# item_url = "https://www.alibaba.com/product-detail/MEISU-CH-Heating-Wood-Burner-Flame_1601731765266.html?spm=a2706.7843667.normalOffer.21.51ea65a51poHRj"

# data = extract_product_data(item_url)
# data


# get_faq_content(driver)
