// GTM Event Logger with Full Data Capture
(function() {
  console.log('GTM Logger Script Version 2.0 - Loading');
  
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
      banner.innerHTML = 'GTM LOGGING ACTIVE (V2.0)';
      
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
  
  // Function to safely extract data for URL transmission
  function safeExtract(obj) {
    if (!obj) return "no";
    
    try {
      var result = "ECOM-DATA:";
      
      // Handle GA4 ecommerce format
      if (obj.items && Array.isArray(obj.items)) {
        result += "GA4|";
        
        if (obj.items.length > 0) {
          var item = obj.items[0];
          var itemData = [];
          
          if (item.item_name) itemData.push("name:" + item.item_name);
          if (item.item_id) itemData.push("id:" + item.item_id);
          if (item.price) itemData.push("$" + item.price);
          
          result += "items[" + obj.items.length + "]|" + itemData.join(",");
        }
        
        if (obj.value) result += "|value:" + obj.value;
      }
      // Handle UA Enhanced Ecommerce format
      else if (obj.detail || obj.add || obj.purchase) {
        result += "UA|";
        
        if (obj.detail) {
          result += "detail|";
          if (obj.detail.products && obj.detail.products.length > 0) {
            var prod = obj.detail.products[0];
            var prodInfo = [];
            if (prod.name) prodInfo.push("name:" + prod.name);
            if (prod.id) prodInfo.push("id:" + prod.id);
            if (prod.price) prodInfo.push("$" + prod.price);
            result += prodInfo.join(",");
          }
        }
        
        if (obj.add) {
          result += "add|";
          if (obj.add.products && obj.add.products.length > 0) {
            var prod = obj.add.products[0];
            var prodInfo = [];
            if (prod.name) prodInfo.push("name:" + prod.name);
            if (prod.id) prodInfo.push("id:" + prod.id);
            if (prod.price) prodInfo.push("$" + prod.price);
            result += prodInfo.join(",");
          }
        }
        
        if (obj.purchase) {
          result += "purchase|";
          if (obj.purchase.actionField && obj.purchase.actionField.revenue) {
            result += "revenue:" + obj.purchase.actionField.revenue;
          }
        }
      }
      // If we can't identify the format, just return raw JSON
      else {
        var json = JSON.stringify(obj);
        if (json.length > 150) {
          json = json.substring(0, 150) + "...";
        }
        result += "RAW|" + json;
      }
      
      return result;
    } catch (e) {
      return "ERROR:" + e.message;
    }
  }
  
  // Function to directly log raw data - absolutely minimal processing
  function directDataExtract(obj) {
    try {
      if (!obj) return "no-data";
      return "RAW-JSON:" + JSON.stringify(obj).substring(0, 200);
    } catch(e) {
      return "ERROR:" + e.message;
    }
  }
  
  // Function to log an event to Google Sheet
  function logToSheet(eventData) {
    try {
      // Extract key information
      var eventName = (eventData.event || 'unknown').toString();
      var page = window.location.pathname;
      var time = new Date().toLocaleTimeString();
      
      // First try the structured extraction
      var ecommerceData = eventData.ecommerce ? safeExtract(eventData.ecommerce) : "no";
      
      // If that fails, fall back to raw data
      if (ecommerceData.indexOf("ERROR:") === 0 && eventData.ecommerce) {
        ecommerceData = directDataExtract(eventData.ecommerce);
      }
      
      // Log to console
      console.log('📊 GTM Event:', eventName, eventData);
      console.log('   Extracted Data:', ecommerceData);
      
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
    
    console.log('GTM monitoring initialized (V2.0)');
    
    // Send initialization confirmation
    if (isLoggingEnabled()) {
      var img = new Image();
      img.src = SHEET_URL + 
                '?time=' + encodeURIComponent(new Date().toLocaleTimeString()) + 
                '&page=' + encodeURIComponent(window.location.pathname) + 
                '&event=' + encodeURIComponent('logger_initialized') + 
                '&ecommerce=' + encodeURIComponent('VERSION:2.0 - Enhanced Data Capture');
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
