import os

def get_credentials():
    return {
        'odoo': {
            'url': os.environ.get('ODOO_URL'),
            'db': os.environ.get('ODOO_DB'),
            'login': os.environ.get('ODOO_LOGIN'),
            'password': os.environ.get('ODOO_PASSWORD')
        },
        'callrail': {
            'api_key': os.environ.get('CALLRAIL_API_KEY'),
            'account_id': os.environ.get('CALLRAIL_ACCOUNT_ID')
        }
    }
