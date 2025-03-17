from playwright.sync_api import sync_playwright
import time
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# Configuration
SERVICE_ACCOUNT_FILE = '/Users/philipantonelli/Downloads/basic-connect-438617-1034321351b2.json'
SPREADSHEET_ID = '1scaHZbpdw_-DE3_CZH7xF4uLo8jXIQzUNjGhfnmRvug'
WORKSHEET_NAME = "mwb_freight_timing"

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate():
    """Authenticate with Google Sheets"""
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return gspread.authorize(credentials)

def get_test_parameters(worksheet):
    """Get parameters from the last complete row"""
    try:
        # Get all rows
        all_rows = worksheet.get_all_values()
        headers = all_rows[0]  # First row is headers
        data_row = all_rows[1]  # Second row has our data
        
        # Get the correct indices (using rindex to find the last occurrence)
        zip_code_idx = 10  # Fixed position for 'Zip Code'
        size_idx = 11      # Fixed position for 'Size'
        size_id_idx = 12   # Fixed position for 'Size ID'
        tray_idx = 13      # Fixed position for 'Tray'
        tray_id_idx = 14   # Fixed position for 'Tray ID'
        
        # Get the values
        zip_code = data_row[zip_code_idx]
        size = data_row[size_idx]
        size_id = data_row[size_id_idx]
        tray = data_row[tray_idx]
        tray_id = data_row[tray_id_idx]
        
        print(f"\nUsing parameters from sheet:")
        print(f"Zip Code: {zip_code}")
        print(f"Size: {size}")
        print(f"Size ID: {size_id}")
        print(f"Tray: {tray}")
        print(f"Tray ID: {tray_id}\n")
        
        return zip_code, size, size_id, tray, tray_id
    
    except Exception as e:
        print(f"Error reading from sheet: {e}")
        return "90210", "4' H X 8' W", "1099", "Marker Tray", "292"
        
def write_to_sheet(sheets, date, timestamp, call_wait, rate, zip_code, size, size_id, tray, tray_id):
    """Write data to Google Sheet"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        worksheet = sheet.worksheet(WORKSHEET_NAME)
        
        # Get all values in column A to find next empty row
        values = worksheet.col_values(1)
        next_row = len(values) + 1
        
        # Write new row using the new syntax
        worksheet.update(
            values=[[date, timestamp, call_wait, rate, zip_code, size, size_id, tray, tray_id]],
            range_name=f'A{next_row}:I{next_row}'
        )
        print(f"Successfully wrote data to row {next_row}")
    except Exception as e:
        print(f"Error writing to sheet: {e}")

def main():
    # First authenticate and get parameters
    sheets = authenticate()
    worksheet = sheets.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    params = get_test_parameters(worksheet)
    
    if not params:
        print("Could not get parameters from sheet. Exiting.")
        return
        
    zip_code, size, size_id, tray, tray_id = params

    with sync_playwright() as p:
        #browser = p.chromium.launch(headless=False, slow_mo=100)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to whiteboard page
        page.goto('https://mywhiteboards.com/great-white-magnetic-whiteboards.html')

        # Wait for size dropdown and select based on parameter
        page.wait_for_selector('#attribute139')
        page.select_option('#attribute139', value=size_id)

        # Wait for marker tray dropdown and select based on parameter
        page.wait_for_selector('#attribute154')
        page.select_option('#attribute154', value=tray_id)

        # Click add to cart button
        page.click('button#product-addtocart-button')

        # Wait for a few seconds after adding to cart
        time.sleep(3)

        # Directly navigate to checkout
        page.goto('https://mywhiteboards.com/checkout/#shipping')
        
        # Wait for checkout page to load
        page.wait_for_selector('div.checkout-container', timeout=60000)

        # Wait for zip code field and fill it
        page.wait_for_selector('input[name="postcode"]')
        page.fill('input[name="postcode"]', zip_code)
        
        # Simulate tab out by pressing Tab
        page.keyboard.press('Tab')
        
        # Start timing
        start_time = time.time()

        # Wait for shipping rates to appear
        try:
            # Wait for either shipping rate or error message
            page.wait_for_selector('.price span.price', timeout=30000)
            
            # Get shipping price
            shipping_price = page.locator('.price span.price').first.inner_text()
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            print(f"Shipping rate found: {shipping_price}")
            print(f"Time taken: {elapsed_time:.2f} seconds")
            
            # Get current date and time
            current_date = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # Write results to sheet
            write_to_sheet(
                sheets, 
                current_date,
                current_time,
                f"{elapsed_time:.2f}",
                shipping_price,
                zip_code,
                size,
                size_id,
                tray,
                tray_id
            )
            
        except Exception as e:
            print(f"Error or timeout waiting for shipping rate: {str(e)}")

        # Keep browser open for a moment before closing
        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    main()
