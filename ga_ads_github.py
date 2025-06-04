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

def fetch_google_ads_data(analytics, days=30):
    """Fetch Google Ads performance data for the last 30 days"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    try:
        print(f"Fetching Google Ads data from {start_date} to {end_date}")
        
        response = analytics.properties().runReport(
            property=f"properties/{GA_PROPERTY_ID}",
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "metrics": [
                    {"name": "advertiserAdCost"},
                    {"name": "advertiserAdClicks"},
                    {"name": "totalRevenue"},
                    {"name": "conversions"}
                ],
                "dimensions": [
                    {"name": "date"},
                    {"name": "sessionCampaignName"}
                ],
                "dimensionFilter": {
                    "filter": {
                        "fieldName": "sessionMedium",
                        "stringFilter": {"matchType": "EXACT", "value": "cpc"}
                    }
                },
                "orderBys": [
                    {"metric": {"metricName": "advertiserAdCost"}, "desc": True}
                ]
            }
        ).execute()
        
        # Headers to match spreadsheet
        headers = [
            "Ads cost",
            "Date", 
            "Session Google Ads campaign",
            "Ads clicks",
            "Purchase revenue",
            "Key event count for purchase"
        ]
        
        # Process the data
        processed_data = []
        
        print(f"Processing {len(response.get('rows', []))} rows from GA4...")
        
        for row in response.get('rows', []):
            # Get date and format it
            date_value = row['dimensionValues'][0]['value']  # Format: YYYYMMDD
            formatted_date = datetime.strptime(date_value, '%Y%m%d').strftime('%Y-%m-%d')
            
            # Get campaign name
            campaign = row['dimensionValues'][1]['value']
            
            # Get metrics
            ads_cost = float(row['metricValues'][0]['value'])
            ads_clicks = int(row['metricValues'][1]['value'])
            revenue = float(row['metricValues'][2]['value'])
            conversions = int(row['metricValues'][3]['value'])
            
            # Include all rows (even with 0 cost for testing)
            processed_data.append([
                ads_cost,        # Ads cost
                formatted_date,  # Date
                campaign,        # Session Google Ads campaign
                ads_clicks,      # Ads clicks
                revenue,         # Purchase revenue
                conversions      # Key event count for purchase
            ])
        
        # Sort by ads cost (descending)
        processed_data.sort(key=lambda x: -x[0])
        
        print(f"Processed {len(processed_data)} rows with Google Ads data")
        
        # Return headers and data
        final_data = [headers] + processed_data
        
        return final_data
        
    except Exception as e:
        print(f"Error fetching Google Ads data: {e}")
        import traceback
        traceback.print_exc()
        return None

def write_to_ga_ads_tab(sheets, data):
    """Write data to the 'ga_ads' tab"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        
        # Check if 'ga_ads' tab exists, if not create it
        try:
            worksheet = sheet.worksheet('ga_ads')
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title='ga_ads', rows=1000, cols=10)
            print("Created new 'ga_ads' worksheet")
        
        # Clear existing data
        worksheet.clear()
        print("Cleared existing data from ga_ads tab")
        
        # Write data starting from A1
        worksheet.update(values=data, range_name="A1")
        print(f"Successfully wrote {len(data)} rows to ga_ads tab")
        
        return True
        
    except Exception as e:
        print(f"Error writing to ga_ads tab: {e}")
        return None

def main():
    print("Starting GA4 Google Ads data collection...")
    
    # Authenticate
    analytics, sheets = authenticate()
    print("Authentication successful")
    
    # Fetch Google Ads data for last 30 days
    print("Fetching Google Ads data for the last 30 days...")
    ads_data = fetch_google_ads_data(analytics, days=30)
    
    if ads_data:
        print("Writing data to ga_ads tab...")
        success = write_to_ga_ads_tab(sheets, ads_data)
        if success:
            print("Process completed successfully!")
        else:
            print("Failed to write data to spreadsheet")
    else:
        print("No data to process")

if __name__ == "__main__":
    main()
