import requests
import json
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
import traceback

# Configuration
CALLRAIL_API_KEY = os.environ.get('CALLRAIL_API_KEY')
CALLRAIL_ACCOUNT_ID = os.environ.get('CALLRAIL_ACCOUNT_ID')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1nHciwKuK_G2wKd4G5i4Fo1gpMNJoscxaDt-LIGHH2EU')
SERVICE_ACCOUNT_FILE = 'service_account.json'
WORKSHEET_NAME = '30-day-callrail'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_sheets():
    """Authenticate with Google Sheets"""
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return gspread.authorize(credentials)

def get_last_30_days_calls():
    """Fetch calls from the last 30 days from CallRail API"""
    api_url = f"https://api.callrail.com/v3/a/{CALLRAIL_ACCOUNT_ID}/calls.json"
    
    # Calculate date range (last 30 days)
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    now_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    thirty_days_ago_iso = thirty_days_ago.strftime('%Y-%m-%dT%H:%M:%SZ')

    headers = {
        'Authorization': f'Token token={CALLRAIL_API_KEY}',
        'Content-Type': 'application/json'
    }

    # Using all available fields that match our needs
    params = {
        'start_date': thirty_days_ago_iso,
        'end_date': now_iso,
        'fields': 'answered,tracking_phone_number,source,start_time,duration,customer_name,customer_phone_number,customer_city,customer_state,customer_country,device_type,keywords,referrer_domain,medium,landing_page_url,campaign,value,recording,agent_email,first_call,note',
        'per_page': 100
    }

    print(f"Fetching calls from {thirty_days_ago_iso} to {now_iso}")
    
    all_calls = []
    page = 1
    
    try:
        while True:
            params['page'] = page
            response = requests.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                calls_data = response.json()
                calls = calls_data.get('calls', [])
                
                if not calls:
                    break
                    
                all_calls.extend(calls)
                print(f"Fetched page {page}, got {len(calls)} calls (total: {len(all_calls)})")
                
                # Check if we have more pages
                if len(calls) < 100:  # Last page
                    break
                    
                page += 1
            else:
                print(f"Failed to retrieve calls. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                break
                
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")

    print(f"Total calls fetched: {len(all_calls)}")
    return all_calls

def prepare_sheet_data(calls):
    """Prepare call data for Google Sheets in tab-separated format"""
    
    # Headers matching your original request
    headers = [
        "Call Status", "Number Name", "Tracking Number", "Source", "Start Time", 
        "Duration (seconds)", "Name", "Phone Number", "Email", "First-Time Caller",
        "City", "State", "Country", "Agent Name", "Agent Number", "Device Type",
        "Keywords", "Referrer", "Medium", "Landing Page", "Campaign", "Value",
        "Recording Url", "Note"
    ]
    
    # Prepare data rows
    rows = [headers]  # Start with headers
    
    for call in calls:
        # Format start time
        start_time = call.get('start_time', '')
        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                start_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        # Determine call status
        call_status = "Answered Call" if call.get('answered', False) else "Missed Call"
        
        # Get recording URL if available
        recording_url = ""
        if call.get('recording'):
            recording_url = f"https://app.callrail.com/calls/{call.get('id', '')}/recording/redirect"
        
        # Prepare row data
        row_data = [
            call_status,                                    # Call Status
            "Number Pool",                                  # Number Name (generic)
            call.get('tracking_phone_number', ''),         # Tracking Number
            call.get('source', ''),                        # Source
            start_time,                                     # Start Time
            str(call.get('duration', 0)),                  # Duration (seconds)
            call.get('customer_name', ''),                 # Name
            call.get('customer_phone_number', ''),         # Phone Number
            '',                                             # Email (not available in API)
            'TRUE' if call.get('first_call', False) else 'FALSE',  # First-Time Caller
            call.get('customer_city', ''),                 # City
            call.get('customer_state', ''),                # State
            call.get('customer_country', ''),              # Country
            call.get('agent_email', ''),                   # Agent Name
            call.get('agent_email', ''),                   # Agent Number (using email)
            call.get('device_type', ''),                   # Device Type
            call.get('keywords', ''),                      # Keywords
            call.get('referrer_domain', ''),               # Referrer
            call.get('medium', ''),                        # Medium
            call.get('landing_page_url', ''),              # Landing Page
            call.get('campaign', ''),                      # Campaign
            str(call.get('value', '')),                    # Value
            recording_url,                                 # Recording Url
            call.get('note', '')                           # Note
        ]
        
        # Clean up the data (replace None with empty string, handle special characters)
        cleaned_row = []
        for item in row_data:
            if item is None:
                item = ''
            # Clean the data for sheets
            item = str(item).replace('\n', ' ').replace('\r', ' ')
            cleaned_row.append(item)
        
        rows.append(cleaned_row)
    
    return rows

def write_to_sheet(sheets, data):
    """Write data to the 30-day-callrail worksheet"""
    try:
        spreadsheet = sheets.open_by_key(SPREADSHEET_ID)
        
        # Check if worksheet exists, create if not
        try:
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Creating new worksheet: {WORKSHEET_NAME}")
            worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=5000, cols=26)
        
        # Clear existing data
        worksheet.clear()
        
        # Add timestamp info
        timestamp_info = [
            [f"CallRail Data - Last 30 Days"],
            [f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
            [f"Total Calls: {len(data) - 1}"],  # Subtract 1 for header row
            []  # Empty row
        ]
        
        # Combine timestamp info with call data
        all_data = timestamp_info + data
        
        # Write all data to sheet
        worksheet.update(values=all_data, range_name="A1")
        
        # Apply formatting
        try:
            # Format header information
            worksheet.format("A1:A3", {
                "textFormat": {"bold": True, "fontSize": 12},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            
            # Format data headers (row 5 after our info rows)
            header_row = 5
            worksheet.format(f"A{header_row}:X{header_row}", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.9},
                "horizontalAlignment": "CENTER"
            })
            
            # Add borders
            data_end_row = len(all_data)
            worksheet.format(f"A{header_row}:X{data_end_row}", {
                "borders": {
                    "top": {"style": "SOLID"},
                    "bottom": {"style": "SOLID"},
                    "left": {"style": "SOLID"},
                    "right": {"style": "SOLID"}
                }
            })
            
            # Freeze header row
            worksheet.freeze(rows=header_row)
            
        except Exception as e:
            print(f"Note: Some formatting could not be applied: {e}")
        
        print(f"Successfully updated '{WORKSHEET_NAME}' worksheet with {len(data)-1} calls")
        return True
        
    except Exception as e:
        print(f"Error writing to sheet: {e}")
        traceback.print_exc()
        return False

def main():
    print("Starting CallRail 30-day data fetch...")
    
    try:
        # Validate environment variables
        if not CALLRAIL_API_KEY or not CALLRAIL_ACCOUNT_ID:
            raise ValueError("Missing required environment variables: CALLRAIL_API_KEY or CALLRAIL_ACCOUNT_ID")
        
        # Authenticate with Google Sheets
        sheets = authenticate_sheets()
        print("Successfully authenticated with Google Sheets")
        
        # Fetch calls from CallRail
        calls = get_last_30_days_calls()
        
        if not calls:
            print("No calls found for the last 30 days")
            return
        
        # Prepare data for sheets
        sheet_data = prepare_sheet_data(calls)
        
        # Write to sheet
        success = write_to_sheet(sheets, sheet_data)
        
        if success:
            print("CallRail data successfully written to Google Sheets!")
            print(f"Check the '{WORKSHEET_NAME}' tab in your spreadsheet")
        else:
            print("Failed to write data to Google Sheets")
            
    except Exception as e:
        print(f"Error in main process: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()
