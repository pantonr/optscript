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

def fetch_daily_metrics(analytics, days=30):
    """Fetch key metrics by day for the dashboard"""
    # Calculate date range
    end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')  # Yesterday
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    try:
        # Make API request to get daily metrics
        response = analytics.properties().runReport(
            property=f"properties/{GA_PROPERTY_ID}",
            body={
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "metrics": [
                    {"name": "sessions"},
                    {"name": "activeUsers"}, 
                    {"name": "screenPageViews"},
                    {"name": "engagementRate"},
                    {"name": "bounceRate"},
                    {"name": "averageSessionDuration"},
                    {"name": "conversions"},
                    {"name": "totalRevenue"}
                ],
                "dimensions": [
                    {"name": "date"}
                ],
                "orderBys": [
                    {"dimension": {"dimensionName": "date"}}
                ]
            }
        ).execute()
        
        # Process the data
        dates = []
        metrics_data = {
            "Sessions": [],
            "Users": [],
            "Page Views": [],
            "Engagement Rate": [],
            "Bounce Rate": [],
            "Avg. Session Duration": [],
            "Conversions": [],
            "Revenue": []
        }
        
        # Get the column headers (metric names) from the response
        metric_headers = [header.get('name') for header in response.get('metricHeaders', [])]
        
        # Process rows of data
        for row in response.get('rows', []):
            # Get date and format it nicely
            date_value = row['dimensionValues'][0]['value']  # Format: YYYYMMDD
            formatted_date = f"{date_value[4:6]}/{date_value[6:8]}/{date_value[0:4]}"
            dates.append(formatted_date)
            
            # Extract metrics
            for i, metric_value in enumerate(row['metricValues']):
                metric_name = metric_headers[i]
                value = metric_value['value']
                
                # Map GA4 metric names to our dashboard names and handle formatting
                if metric_name == 'sessions':
                    metrics_data["Sessions"].append(int(float(value)))
                elif metric_name == 'activeUsers':
                    metrics_data["Users"].append(int(float(value)))
                elif metric_name == 'screenPageViews':
                    metrics_data["Page Views"].append(int(float(value)))
                elif metric_name == 'engagementRate':
                    # Convert decimal to percentage
                    metrics_data["Engagement Rate"].append(f"{float(value)*100:.2f}%")
                elif metric_name == 'bounceRate':
                    # Convert decimal to percentage
                    metrics_data["Bounce Rate"].append(f"{float(value)*100:.2f}%")
                elif metric_name == 'averageSessionDuration':
                    # Format seconds to MM:SS
                    seconds = int(float(value))
                    minutes = seconds // 60
                    remaining_seconds = seconds % 60
                    metrics_data["Avg. Session Duration"].append(f"{minutes}:{remaining_seconds:02d}")
                elif metric_name == 'conversions':
                    metrics_data["Conversions"].append(int(float(value)))
                elif metric_name == 'totalRevenue':
                    # Format as currency
                    metrics_data["Revenue"].append(f"${float(value):.2f}")
        
        # Calculate totals and averages
        summary = {
            "Sessions": sum(int(str(x).replace(',', '')) for x in metrics_data["Sessions"]),
            "Users": sum(int(str(x).replace(',', '')) for x in metrics_data["Users"]),
            "Page Views": sum(int(str(x).replace(',', '')) for x in metrics_data["Page Views"]),
            # Calculate weighted averages for rates
            "Engagement Rate": f"{sum(float(str(x).replace('%', '')) for x in metrics_data['Engagement Rate']) / len(metrics_data['Engagement Rate']):.2f}%",
            "Bounce Rate": f"{sum(float(str(x).replace('%', '')) for x in metrics_data['Bounce Rate']) / len(metrics_data['Bounce Rate']):.2f}%",
            # Format average duration
            "Avg. Session Duration": calculate_avg_duration(metrics_data["Avg. Session Duration"]),
            "Conversions": sum(int(str(x).replace(',', '')) for x in metrics_data["Conversions"]),
            "Revenue": f"${sum(float(str(x).replace('$', '').replace(',', '')) for x in metrics_data['Revenue']):.2f}"
        }
        
        # Calculate day-over-day changes (percentage)
        daily_changes = calculate_daily_changes(metrics_data)
        
        # Calculate overall change (latest day vs first day)
        overall_changes = calculate_overall_changes(metrics_data)
        
        # Format data for Google Sheets
        date_range_info = [f"Last 30 Days ({start_date} to {end_date})"]  # Changed to 30 days
        header = ["Metric"] + dates + ["Total/Avg", "Change"]
        
        # Create data rows
        rows = []
        for metric_name in metrics_data:
            row = [metric_name] + metrics_data[metric_name] + [summary[metric_name]] + [overall_changes[metric_name]]
            rows.append(row)
        
        # Add daily change rows
        daily_change_rows = []
        for metric_name in daily_changes:
            row = [f"{metric_name} Daily Change"] + daily_changes[metric_name]
            daily_change_rows.append(row)
        
        # Combine everything
        dashboard_data = [date_range_info, [], header] + rows + [[], ["Daily Changes"]] + daily_change_rows
        
        # Add chart data
        chart_data = prepare_chart_data(dates, metrics_data)
        dashboard_data += chart_data
        
        return dashboard_data
        
    except Exception as e:
        print(f"Error fetching dashboard metrics: {e}")
        return None

def calculate_avg_duration(duration_list):
    """Calculate average session duration from a list of MM:SS format strings"""
    total_seconds = 0
    for duration in duration_list:
        parts = duration.split(':')
        minutes = int(parts[0])
        seconds = int(parts[1])
        total_seconds += (minutes * 60) + seconds
    
    avg_seconds = total_seconds // len(duration_list)
    avg_minutes = avg_seconds // 60
    avg_remaining_seconds = avg_seconds % 60
    return f"{avg_minutes}:{avg_remaining_seconds:02d}"

def calculate_daily_changes(metrics_data):
    """Calculate day-over-day percentage changes for each metric"""
    daily_changes = {}
    
    for metric_name, values in metrics_data.items():
        daily_changes[metric_name] = []
        
        # Skip first day as we can't calculate change
        daily_changes[metric_name].append("")
        
        for i in range(1, len(values)):
            try:
                # Clean values (remove commas, $, % symbols)
                current_value = float(str(values[i]).replace('%', '').replace('$', '').replace(',', ''))
                previous_value = float(str(values[i-1]).replace('%', '').replace('$', '').replace(',', ''))
                
                # Handle special case for time format (MM:SS)
                if metric_name == "Avg. Session Duration":
                    current_parts = str(values[i]).split(':')
                    previous_parts = str(values[i-1]).split(':')
                    current_value = (int(current_parts[0]) * 60) + int(current_parts[1])
                    previous_value = (int(previous_parts[0]) * 60) + int(previous_parts[1])
                
                # Calculate percentage change
                if previous_value == 0:
                    change = "∞" if current_value > 0 else "0.00%"
                else:
                    change_pct = ((current_value - previous_value) / previous_value) * 100
                    
                    # Format with arrow indicators
                    if change_pct > 0:
                        change = f"↑{change_pct:.2f}%"
                    elif change_pct < 0:
                        change = f"↓{abs(change_pct):.2f}%"
                    else:
                        change = "0.00%"
                
                daily_changes[metric_name].append(change)
            except:
                daily_changes[metric_name].append("N/A")
        
    return daily_changes

def calculate_overall_changes(metrics_data):
    """Calculate percentage change between first and last day"""
    overall_changes = {}
    
    for metric_name, values in metrics_data.items():
        try:
            # Clean values (remove commas, $, % symbols)
            last_value = float(str(values[-1]).replace('%', '').replace('$', '').replace(',', ''))
            first_value = float(str(values[0]).replace('%', '').replace('$', '').replace(',', ''))
            
            # Handle special case for time format (MM:SS)
            if metric_name == "Avg. Session Duration":
                last_parts = str(values[-1]).split(':')
                first_parts = str(values[0]).split(':')
                last_value = (int(last_parts[0]) * 60) + int(last_parts[1])
                first_value = (int(first_parts[0]) * 60) + int(first_parts[1])
            
            # Calculate percentage change
            if first_value == 0:
                change = "∞" if last_value > 0 else "0.00%"
            else:
                change_pct = ((last_value - first_value) / first_value) * 100
                
                # Format with arrow indicators
                if change_pct > 0:
                    change = f"↑{change_pct:.2f}%"
                elif change_pct < 0:
                    change = f"↓{abs(change_pct):.2f}%"
                else:
                    change = "0.00%"
            
            overall_changes[metric_name] = change
        except:
            overall_changes[metric_name] = "N/A"
    
    return overall_changes

def prepare_chart_data(dates, metrics_data):
    """Format data for potential charts"""
    # This returns data that can be used for charting in Google Sheets
    # Add 3 empty rows as a separator
    chart_data = [[], [], []]
    
    # Add chart data for sessions and users (most common metrics to chart)
    chart_data.append(["Chart Data (for reference)"])
    chart_data.append([])
    chart_data.append(["Date"] + dates)
    chart_data.append(["Sessions"] + metrics_data["Sessions"])
    chart_data.append(["Users"] + metrics_data["Users"])
    chart_data.append(["Page Views"] + metrics_data["Page Views"])
    
    return chart_data


def write_to_thirty_day_view(sheets, data):
    """Write data to a tab named '30-Day View'"""
    try:
        sheet = sheets.open_by_key(SPREADSHEET_ID)
        
        # Check if '30-Day View' tab exists, if not create it
        try:
            worksheet = sheet.worksheet('30-Day View')
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title='30-Day View', rows=50, cols=35)  # Wider for more days
        
        # Clear existing data
        worksheet.clear()
        
        # Write data (using named parameters to avoid deprecation warning)
        worksheet.update(values=data, range_name="A1")
        
        # Apply formatting
        try:
            # Format title
            worksheet.format("A1:AE1", {  # Wider range for 30 days
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True, "fontSize": 12},
                "horizontalAlignment": "CENTER"
            })
            
            # Format main header row
            header_row = 3
            worksheet.format(f"A{header_row}:AE{header_row}", {  # Wider range for 30 days
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.9},
                "horizontalAlignment": "CENTER"
            })
            
            # Format metric names column
            worksheet.format("A4:A12", {"textFormat": {"bold": True}})
            
            # Format the Total/Avg column - Need to adapt for the right column with 30 days
            metrics_count = 8  # Number of main metrics
            col_count = 30 + 2  # 30 days + Metric name + Total
            total_col_letter = chr(64 + col_count)  # Convert to letter (e.g., 32 -> AF)
            
            worksheet.format(f"{total_col_letter}4:{total_col_letter}{4+metrics_count}", {
                "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.8},
                "textFormat": {"bold": True}
            })
            
            # Format the Change column - Need to adapt for the right column with 30 days
            change_col_letter = chr(65 + col_count)  # Convert to letter (e.g., 33 -> AG)
            
            worksheet.format(f"{change_col_letter}4:{change_col_letter}{4+metrics_count}", {
                "backgroundColor": {"red": 0.95, "green": 0.8, "blue": 0.8},
                "textFormat": {"bold": True}
            })
            
            # Format daily changes section
            daily_changes_row = 4 + metrics_count + 2
            worksheet.format(f"A{daily_changes_row}", {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True}
            })
            
            worksheet.format(f"A{daily_changes_row+1}:A{daily_changes_row+metrics_count}", {
                "textFormat": {"bold": True, "italic": True}
            })
            
            # Format chart data section
            chart_data_row = daily_changes_row + metrics_count + 4
            worksheet.format(f"A{chart_data_row}", {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True}
            })
            worksheet.format(f"A{chart_data_row+2}", {"textFormat": {"bold": True}})
            
            # Add conditional formatting for positive/negative changes for daily changes
            # When we have 30 days, this range needs to be wider
            worksheet.conditional_format(f"B{4+metrics_count+1}:AE{4+metrics_count+metrics_count}", {
                "type": "TEXT_CONTAINS",
                "values": [["↑"]],
                "textFormat": {"foregroundColor": {"red": 0.0, "green": 0.6, "blue": 0.0}}
            })
            
            worksheet.conditional_format(f"B{4+metrics_count+1}:AE{4+metrics_count+metrics_count}", {
                "type": "TEXT_CONTAINS",
                "values": [["↓"]],
                "textFormat": {"foregroundColor": {"red": 0.8, "green": 0.0, "blue": 0.0}}
            })
            
            # Add borders with wider range for 30 days
            worksheet.format("A1:AE50", {
                "borders": {
                    "top": {"style": "SOLID"},
                    "bottom": {"style": "SOLID"},
                    "left": {"style": "SOLID"},
                    "right": {"style": "SOLID"}
                }
            })
            
        except Exception as f:
            print(f"Note: Some formatting could not be applied: {f}")
        
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
        success = write_to_thirty_day_view(sheets, dashboard_data)
        if success:
            print("Process completed successfully! Dashboard data written to '30-Day View' tab")
    else:
        print("No data to process")

if __name__ == "__main__":
    main()
