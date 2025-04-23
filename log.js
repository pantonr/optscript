// GTM Event Logger with Full Data + JSON Capture
(function() {
  console.log('GTM Logger Script Version 3.0 - Loading');
  
  // Storage key for enabling/disabling logging
  var LOGGER_ENABLED_KEY = 'gtm_logger_enabled';
  
  // Google Sheet URL
  var SHEET_URL = 'https://script.google.com/macros/s/AKfycbxIl3Enffr6mH37xtOQsFajDwBZYE9JAyIqDIAqYHmFbEaW5Dhu25gJRmhLTm-a4zVo/exec';
  
  // Check if URL has logs parameter
  if (window.location.href.indexOf('logs') > -1) {
    // Enable logging via localStorage
    localStorage.setItem(LOGGER_ENABLED_KEY, 'true');
    console.log('GTM Logger Enabled via URL parameter');
  }
  
  // Function to check if logging is enabled
  function isLoggingEnabled() {
    return localStorage.getItem(LOGGER_ENABLED_KEY) === 'true';
  }
  
  // Function to create or update banner
  function updateBanner() {
    // Remove existing banner if present
    var existingBanner = document.getElementById('gtm-logger-banner');
    if (existingBanner) {
      existingBanner.remove();
    }
    
    // Create new banner if logging is enabled
    if (isLoggingEnabled() && document.body) {
      var banner = document.createElement('div');
      banner.id = 'gtm-logger-banner';
      banner.style.position = 'fixed';
      banner.style.top = '0';
      banner.style.left = '0';
      banner.style.width = '100%';
      banner.style.background = 'red';
      banner.style.color = 'white';
      banner.style.padding = '10px';
      banner.style.textAlign = 'center';
      banner.style.zIndex = '9999999';
      banner.innerHTML = 'GTM LOGGING ACTIVE (V3.0 with JSON)';
      
      // Add disable button
      var disableBtn = document.createElement('button');
      disableBtn.innerHTML = 'Disable Logging';
      disableBtn.style.marginLeft = '10px';
      disableBtn.onclick = function() {
        localStorage.removeItem(LOGGER_ENABLED_KEY);
        updateBanner();
      };
      banner.appendChild(disableBtn);
      
      document.body.appendChild(banner);
    }
  }
  
  // Function to safely get JSON representation
  function safeJsonStringify(obj, maxLength) {
    if (!obj) return "";
    if (maxLength === undefined) maxLength = 250;
    
    try {
      var json = JSON.stringify(obj);
      if (json.length > maxLength) {
        json = json.substring(0, maxLength) + "...";
      }
      return json;
    } catch (e) {
      return "Error: " + e.message;
    }
  }
  
  // Function to log an event to Google Sheet
  function logToSheet(eventData) {
    try {
      // Extract key information
      var eventName = (eventData.event || 'unknown').toString();
      var page = window.location.pathname;
      var time = new Date().toLocaleTimeString();
      
      // Get the raw JSON of ecommerce data
      var rawJson = "";
      if (eventData.ecommerce) {
        rawJson = safeJsonStringify(eventData.ecommerce, 250);
      }
      
      // Format: Use the DIRECT_EXTRACT format that we know works
      var ecommerceData = "no";
      if (eventData.ecommerce) {
        try {
          ecommerceData = "DIRECT_EXTRACT: ";
          
          // For GA4
          if (eventData.ecommerce.items) {
            ecommerceData += "GA4 | items[" + eventData.ecommerce.items.length + "]";
            
            // First item details
            if (eventData.ecommerce.items.length > 0) {
              ecommerceData += " | first_item:" + safeJsonStringify(eventData.ecommerce.items[0], 100);
            }
            
            // Value if present
            if (eventData.ecommerce.value) {
              ecommerceData += " | value:" + eventData.ecommerce.value;
            }
          }
          // For UA Enhanced Ecommerce
          else if (eventData.ecommerce.detail || eventData.ecommerce.add || eventData.ecommerce.purchase) {
            ecommerceData += "UA | ";
            
            if (eventData.ecommerce.detail) {
              ecommerceData += "detail | ";
              if (eventData.ecommerce.detail.products) {
                ecommerceData += "products:" + safeJsonStringify(eventData.ecommerce.detail.products, 100);
              }
            }
            
            if (eventData.ecommerce.add) {
              ecommerceData += "add | ";
              if (eventData.ecommerce.add.products) {
                ecommerceData += "products:" + safeJsonStringify(eventData.ecommerce.add.products, 100);
              }
            }
            
            if (eventData.ecommerce.purchase) {
              ecommerceData += "purchase | ";
              if (eventData.ecommerce.purchase.actionField) {
                ecommerceData += "transaction:" + safeJsonStringify(eventData.ecommerce.purchase.actionField, 100);
              }
            }
          }
          // For unknown formats
          else {
            ecommerceData += "UNKNOWN | raw:" + safeJsonStringify(eventData.ecommerce, 100);
          }
        } catch (err) {
          ecommerceData = "ERROR: " + err.message;
        }
      }
      
      // Log to console
      console.log('📊 GTM Event:', eventName, eventData);
      console.log('   Extracted:', ecommerceData);
      console.log('   Raw JSON:', rawJson);
      
      // Add raw JSON to the data
      ecommerceData += " || JSON:" + rawJson;
      
      // Send to Google Sheet via image request
      var img = new Image();
      img.src = SHEET_URL + 
                '?time=' + encodeURIComponent(time) + 
                '&page=' + encodeURIComponent(page) + 
                '&event=' + encodeURIComponent(eventName) + 
                '&ecommerce=' + encodeURIComponent(ecommerceData);
                
      // Add to DOM briefly to ensure request goes through
      img.style.display = 'none';
      document.body.appendChild(img);
      
      // Remove after request is sent
      setTimeout(function() {
        if (img.parentNode) img.parentNode.removeChild(img);
      }, 1000);
      
    } catch(e) {
      console.error('Error logging to sheet:', e);
      
      // Last resort - try to send error info
      try {
        var img = new Image();
        img.src = SHEET_URL + 
                  '?time=' + encodeURIComponent(new Date().toLocaleTimeString()) + 
                  '&page=' + encodeURIComponent(window.location.pathname) + 
                  '&event=' + encodeURIComponent('error_in_logger') + 
                  '&ecommerce=' + encodeURIComponent('ERROR:' + e.message);
        img.style.display = 'none';
        document.body.appendChild(img);
      } catch(e2) {
        // Nothing more we can do
      }
    }
  }
  
  // Set up dataLayer monitoring
  function setupMonitoring() {
    // Only set up once
    if (window._gtmMonitorSetup) return;
    window._gtmMonitorSetup = true;
    
    // Create dataLayer if it doesn't exist
    window.dataLayer = window.dataLayer || [];
    
    // Store original push method
    var originalPush = window.dataLayer.push;
    
    // Replace with our monitored version
    window.dataLayer.push = function() {
      // Call original method
      var result = originalPush.apply(this, arguments);
      
      // Log if enabled and we have valid data
      if (isLoggingEnabled() && arguments[0] && typeof arguments[0] === 'object') {
        logToSheet(arguments[0]);
      }
      
      return result;
    };
    
    console.log('GTM monitoring initialized (V3.0 with JSON)');
    
    // Send initialization confirmation
    if (isLoggingEnabled()) {
      var img = new Image();
      img.src = SHEET_URL + 
                '?time=' + encodeURIComponent(new Date().toLocaleTimeString()) + 
                '&page=' + encodeURIComponent(window.location.pathname) + 
                '&event=' + encodeURIComponent('logger_initialized') + 
                '&ecommerce=' + encodeURIComponent('VERSION:3.0 - With full JSON data');
      img.style.display = 'none';
      document.body.appendChild(img);
    }
  }
  
  // Initialize
  function init() {
    // Setup monitoring
    setupMonitoring();
    
    // Update banner if body exists
    if (document.body) {
      updateBanner();
    } else {
      // Try again soon if body isn't ready
      setTimeout(updateBanner, 500);
    }
  }
  
  // Run initialization
  init();
  
  // Also check periodically to ensure banner stays visible (for SPAs and dynamic content)
  setInterval(updateBanner, 1000);
})();
