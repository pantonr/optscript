from playwright.sync_api import sync_playwright
import logging
import time
import os  # Add this import

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_odoo_scheduler(headless=True):
    logging.info(f"Running in {'headless' if headless else 'visible'} mode")
    
    # Get credentials from GitHub Secrets
    username = os.environ.get('ODOO_USERNAME')
    password = os.environ.get('ODOO_PASSWORD')

    if not username or not password:
        raise ValueError("Missing required environment variables ODOO_USERNAME or ODOO_PASSWORD")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Start with login page
            logging.info("Navigating to login page...")
            page.goto("https://odoo.optimacompanies.com/web/login")
            
            # Fill in login form using secrets
            logging.info("Filling in login details...")
            page.fill("input[name='login']", username)
            page.fill("input[name='password']", password)

            # Click login button
            logging.info("Attempting to click login button...")
            page.click("div.oe_login_buttons button[type='submit']")
            
            # Wait for home page to load completely
            logging.info("Waiting for home page to load...")
            page.wait_for_load_state('networkidle')
            page.wait_for_selector(".o_main_navbar", state="visible", timeout=20000)
            time.sleep(3)  # Increased wait time after login
            


            # Navigate to scheduler with longer timeout
            logging.info("Navigating to scheduler page...")
            try:
                page.goto("https://odoo.optimacompanies.com/web#id=62&cids=1&menu_id=29&action=13&model=ir.cron&view_type=form")
                time.sleep(2)  # Just fucking wait
                
                # Check if we're on the right page and click the damn button
                logging.info("Checking for scheduler button...")
                button = page.locator("text=Run Manually").first
                button.click(force=True)
                logging.info("Button clicked")
                time.sleep(2)  # Keep browser open to see the click


            except Exception as e:
                logging.error(f"Error during scheduler navigation/operation: {str(e)}")
                raise


                
        finally:
            logging.info("Closing browser...")
            context.close()
            browser.close()

if __name__ == "__main__":
    logging.info("Starting script...")
    try:
        # For local testing, set headless=False to see the browser
        # For GitHub Actions, set headless=True
        run_odoo_scheduler(headless=True)  # Set to False to see the browser
        logging.info("Script completed successfully")
    except Exception as e:
        logging.error(f"Script failed: {str(e)}")
