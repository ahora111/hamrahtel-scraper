import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from googleapiclient.discovery import build
from persiantools.jdatetime import JalaliDate
import os
import time

CREDENTIALS_FILE = "temp_credentials.json"

def create_credentials_file():
    secret = os.getenv("CREDENTIALS_JSON")
    if not secret:
        print("❌ Secret مربوط به credentials.json پیدا نشد!")
        return False
    try:
        with open(CREDENTIALS_FILE, "w") as f:
            f.write(secret)
        return True
    except Exception as e:
        print(f"❌ خطا در ساخت فایل credentials.json: {e}")
        return False

def remove_credentials_file():
    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)

def get_google_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

def open_worksheet(client, spreadsheet_key):
    spreadsheet = client.open_by_key(spreadsheet_key)
    worksheet = spreadsheet.get_worksheet(0)
    return worksheet

def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def scroll_page(driver, scroll_pause_time=2):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def extract_product_data(driver, valid_brands):
    product_elements = driver.find_elements(By.CLASS_NAME, 'mantine-Text-root')
    brands, models, dates = [], [], []
    for product in product_elements:
        name = product.text.strip().replace("تومانءء", "").replace("تومان", "").replace("نامشخص", "").strip()
        parts = name.split()
        brand = parts[0] if len(parts) >= 2 else name
        model = " ".join(parts[1:]) if len(parts) >= 2 else ""
        if brand in valid_brands:
            brands.append(brand)
            models.append(model)
            dates.append("")
        else:
            models.append(brand + " " + model)
            brands.append("")
            dates.append("")
    return brands[25:], models[25:], dates[25:]

def is_number(model_str):
    try:
        float(model_str.replace(",", ""))
        return True
    except ValueError:
        return False

def process_model(model_str):
    model_str = model_str.replace("٬", "").replace(",", "").strip()
    if is_number(model_str):
        model_value = float(model_str)
        model_value_with_increase = model_value * 1.015
        return f"{model_value_with_increase:,.0f}"
    return model_str

def write_data_to_sheet(worksheet, models, brands):
    worksheet.clear()
    worksheet.append_row(["مدل", "برند", "تاریخ بروزرسانی"])
    data_to_insert = []
    for i in range(len(brands)):
        model_str = process_model(models[i])
        data_to_insert.append([model_str, brands[i], JalaliDate.today().strftime("%Y-%m-%d")])
    worksheet.append_rows(data_to_insert)

def batch_update_cell_colors(service, spreadsheet_id, models):
    requests = []
    for row_num, model in enumerate(models, start=2):
        color = {"red": 1.0, "green": 1.0, "blue": 0.8} if any(keyword in model for keyword in ["RAM", "Non Active", "FA", "Classic"]) else {"red": 0.85, "green": 0.85, "blue": 0.85}
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": 0,
                    "startRowIndex": row_num - 1,
                    "endRowIndex": row_num,
                    "startColumnIndex": 0,
                    "endColumnIndex": 3
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": color
                    }
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        })
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()

def main():
    if not create_credentials_file():
        return
    try:
        client = get_google_sheets_client()
        worksheet = open_worksheet(client, "1Su9BwqFlB2Y6JwG0LLRKQfNN2z090egjDySyX7zEvYw")
        driver = get_driver()
        driver.get('https://hamrahtel.com/quick-checkout')
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'mantine-Text-root')))
        print("✅ داده‌ها آماده‌ی استخراج هستند!")
        scroll_page(driver)
        valid_brands = ["Galaxy", "POCO", "Redmi", "iPhone", "Redtone", "VOCAL", "TCL", "NOKIA", "Honor", "Huawei", "GLX", "+Otel"]
        brands, models, dates = extract_product_data(driver, valid_brands)
        if brands:
            write_data_to_sheet(worksheet, models, brands)
            print("✅ داده‌ها با موفقیت در Google Sheets ذخیره شدند!")
        else:
            print("❌ داده‌ای برای ذخیره وجود ندارد!")
        service = build('sheets', 'v4', credentials=ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]))
        batch_update_cell_colors(service, "1Su9BwqFlB2Y6JwG0LLRKQfNN2z090egjDySyX7zEvYw", models)
        driver.quit()
    except Exception as e:
        print(f"❌ خطا: {e}")
    finally:
        remove_credentials_file()

if __name__ == "__main__":
    main()
