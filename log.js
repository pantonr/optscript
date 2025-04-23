// GTM Event Logger with Enhanced Ecommerce Data
(function() {
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
      banner.innerHTML = 'GTM LOGGING ACTIVE';
      
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
  
  // Function to safely extract ecommerce data
  function getEcommerceDetails(ecomObj) {
    if (!ecomObj) return "no";
    
    try {
      var details = [];
      
      // Check for GA4 format
      if (ecomObj.items && Array.isArray(ecomObj.items)) {
        details.push("items:" + ecomObj.items.length);
        
        // Get first item details
        if (ecomObj.items.length > 0) {
          var item = ecomObj.items[0];
          if (item.item_name) details.push("name:" + item.item_name);
          if (item.item_id) details.push("id:" + item.item_id);
          if (item.price) details.push("price:" + item.price);
        }
        
        // Get value if present
        if (ecomObj.value) details.push("value:" + ecomObj.value);
      }
      
      // Enhanced Ecommerce format (UA)
      var actions = ["detail", "add", "remove", "checkout", "purchase"];
      actions.forEach(function(action) {
        if (ecomObj[action]) {
          details.push("action:" + action);
          
          // Get products
          if (ecomObj[action].products && ecomObj[action].products.length > 0) {
            var product = ecomObj[action].products[0];
            if (product.name) details.push("name:" + product.name);
            if (product.id) details.push("id:" + product.id);
            if (product.price) details.push("price:" + product.price);
          }
          
          // Get transaction data
          if (action === "purchase" && ecomObj[action].actionField) {
            var af = ecomObj[action].actionField;
            if (af.id) details.push("transaction:" + af.id);
            if (af.revenue) details.push("revenue:" + af.revenue);
          }
        }
      });
      
      // If we got details, return them
      if (details.length > 0) {
        return details.join(" | ");
      }
      
      // Otherwise, return a short version of the object
      var shortJson = JSON.stringify(ecomObj).substring(0, 200);
      return shortJson;
      
    } catch (e) {
      return "error parsing ecommerce data";
    }
  }
  
  // Function to log an event to Google Sheet
  function logToSheet(eventData) {
    try {
      // Extract key information
      var eventName = (eventData.event || 'unknown').toString();
      var page = window.location.pathname;
      var time = new Date().toLocaleTimeString();
      
      // Get detailed ecommerce information
      var ecommerceDetails = eventData.ecommerce ? 
                           getEcommerceDetails(eventData.ecommerce) : 
                           "no";
      
      // Log to console
      console.log('📊 GTM Event:', eventName, eventData);
      
      // Send to Google Sheet via image request
      var img = new Image();
      img.src = SHEET_URL + 
                '?time=' + encodeURIComponent(time) + 
                '&page=' + encodeURIComponent(page) + 
                '&event=' + encodeURIComponent(eventName) + 
                '&ecommerce=' + encodeURIComponent(ecommerceDetails);
                
      // Add to DOM briefly to ensure request goes through
      img.style.display = 'none';
      document.body.appendChild(img);
      
      // Remove after request is sent
      setTimeout(function() {
        if (img.parentNode) img.parentNode.removeChild(img);
      }, 1000);
      
    } catch(e) {
      console.error('Error logging to sheet:', e);
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
    
    console.log('GTM monitoring initialized');
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
