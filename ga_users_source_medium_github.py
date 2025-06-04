from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread
from datetime import datetime, timedelta
import os

# Configuration - modified for GitHub Actions
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_ID = '1nHciwKuK_G2wKd4G5i4Fo1gpMNJoscxaDt-LIGHH2EU'
GA_PROPERTY_ID = '327739759'

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

def fetch_user_source_medium_data(analytics, days=30):
    """Fetch user data with first user source and medium for the last 30 days"""
    # Calculate date range - current day minus specified days
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    try:
        print(f"Fetching data from {start_date} to {end_date}")
        
        response = analytics.properties().runReport(
            property=f"properties/{GA_PROPERTY_ID}",
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "metrics": [
                    {"name": "totalUsers"}
                ],
                "dimensions": [
                    {"name": "date"},
                    {"name": "firstUserSource"},
                    {"name": "firstUserMedium"}
                ],
                "orderBys": [
                    {"dimension": {"dimensionName": "date"}},
                    {"metric": {"metricName": "totalUsers"}, "desc": True}
                ]
            }
        ).execute()
        
        # Headers to match spreadsheet
        headers = [
            "date_order",
            "Total users",
            "First user source",
            "First user medium", 
            "Date"
        ]
        
        # Process the data
        processed_data = []
        
        print(f"Processing {len(response.get('rows', []))} rows from GA4...")
        
        for row in response.get('rows', []):
            # Get date and format it
            date_value = row['dimensionValues'][0]['value']  # Format: YYYYMMDD
            formatted_date = datetime.strptime(date_value, '%Y%m%d').strftime('%Y-%m-%d')
            
            # Get dimensions
            first_user_source = row['dimensionValues'][1]['value']
            first_user_medium = row['dimensionValues'][2]['value']
            
            # Get metrics
            users = int(row['metricValues'][0]['value'])
            
            # Skip rows with 0 users to keep data clean
            if users > 0:
                processed_data.append([
                    formatted_date,  # date_order column
                    users,           # Total users
                    first_user_source, # First user source
                    first_user_medium, # First user medium
                    formatted_date   # Date column (duplicate for matching format)
                ])
        
        # Sort by date and then by users (descending)
        processed_data.sort(key=lambda x: (x[0], -x[1]))
        
        print(f"Processed {len(processed_data)} rows with user data")
        
        # Return just headers and data (no extra summary rows)
        final_data = [headers] + processed_data
        
        return final_data
        
    except Exception as e:
        print(f"Error fetching user source/medium data: {e}")
        return None

def write_to_ga_users_tab(sheets, data):
    """Write data to the 'ga_users' tab"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        
        # Check if 'ga_users' tab exists, if not create it
        try:
            worksheet = sheet.worksheet('ga_users')
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title='ga_users', rows=1000, cols=10)
            print("Created new 'ga_users' worksheet")
        
        # Clear existing data
        worksheet.clear()
        print("Cleared existing data from ga_users tab")
        
        # Write data starting from A1
        worksheet.update(values=data, range_name="A1")
        print(f"Successfully wrote {len(data)} rows to ga_users tab")
        
        # Apply basic formatting
        try:
            # Format header row
            worksheet.format("A1:E1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.9}
            })
            
            # Format date columns
            data_end_row = len(data)
            worksheet.format(f"A2:A{data_end_row}", {
                "numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}
            })
            worksheet.format(f"E2:E{data_end_row}", {
                "numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}
            })
            
            # Format users column (numbers)
            worksheet.format(f"B2:B{data_end_row}", {
                "numberFormat": {"type": "NUMBER", "pattern": "#,##0"}
            })
            
        except Exception as f:
            print(f"Note: Some formatting could not be applied: {f}")
        
        print(f"Successfully updated 'ga_users' tab")
        
        return True
        
    except Exception as e:
        print(f"Error writing to ga_users tab: {e}")
        return None

def main():
    print("Starting GA4 user source/medium data collection...")
    
    # Authenticate
    analytics, sheets = authenticate()
    print("Authentication successful")
    
    # Fetch user data for last 30 days
    print("Fetching user data for the last 30 days...")
    user_data = fetch_user_source_medium_data(analytics, days=30)
    
    if user_data:
        print("Writing data to ga_users tab...")
        success = write_to_ga_users_tab(sheets, user_data)
        if success:
            print("Process completed successfully!")
        else:
            print("Failed to write data to spreadsheet")
    else:
        print("No data to process")

if __name__ == "__main__":
    main()
