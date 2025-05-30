from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread
from datetime import datetime, timedelta
import os

# Configuration - modified for GitHub Actions
SERVICE_ACCOUNT_FILE = 'service_account.json'  # This file will be created by GitHub Actions
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1nHciwKuK_G2wKd4G5i4Fo1gpMNJoscxaDt-LIGHH2EU')
GA_PROPERTY_ID = os.environ.get('GA_PROPERTY_ID', '327739759')

SCOPES = [
    'https://www.googleapis.com/auth/analytics.readonly',
    'https://www.googleapis.com/auth/spreadsheets'
]

def authenticate():
    """Authenticate with Google services"""
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    analytics = build('analyticsdata', 'v1beta', credentials=credentials)
    sheets = gspread.authorize(credentials)
    return analytics, sheets

def fetch_daily_metrics(analytics, days=30):  # Changed to 30 days
    """Fetch key metrics by day for the dashboard"""
    # Calculate date range
    end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')  # Yesterday
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # The rest of the function is the same as in your 7-day script
    # [... Same code as in your original script ...]

# All other functions remain the same, just like in your 7-day script

def write_to_thirty_day_view(sheets, data):  # Changed function name
    """Write data to a tab named '30-Day View'"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        
        # Check if '30-Day View' tab exists, if not create it
        try:
            worksheet = sheet.worksheet('30-Day View')  # Changed tab name
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title='30-Day View', rows=50, cols=35)  # Wider for more days
        
        # Clear existing data
        worksheet.clear()
        
        # Write data (using named parameters to avoid deprecation warning)
        worksheet.update(values=data, range_name="A1")
        
        # Apply formatting - same as your 7-day view but with wider ranges where needed
        # [... Same formatting code as in your original script ...]
        
        print(f"Successfully updated '30-Day View' tab with dashboard data.")
        
        return True
        
    except Exception as e:
        print(f"Error writing to sheet: {e}")
        return None

def main():
    print("Starting GA4 30-day dashboard data collection process...")
    analytics, sheets = authenticate()
    print("Authentication successful")
    
    print("Fetching website metrics for the last 30 days...")
    dashboard_data = fetch_daily_metrics(analytics, days=30)  # Changed to 30 days
    
    if dashboard_data:
        print("Writing data to 30-Day View tab...")
        success = write_to_thirty_day_view(sheets, dashboard_data)  # Changed function call
        if success:
            print("Process completed successfully! Dashboard data written to '30-Day View' tab")
    else:
        print("No data to process")

if __name__ == "__main__":
    main()
