// GTM Event Logger with Enhanced Data Capture
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
  
  // Helper function to safely extract data from complex objects
  function safeExtract(obj, path) {
    try {
      var parts = path.split('.');
      var current = obj;
      for (var i = 0; i < parts.length; i++) {
        if (current[parts[i]] === undefined) return null;
        current = current[parts[i]];
      }
      return current;
    } catch (e) {
      return null;
    }
  }
  
  // Function to extract meaningful ecommerce data
  function extractEcommerceData(eventData) {
    if (!eventData.ecommerce) return "no";
    
    var result = [];
    var ecom = eventData.ecommerce;
    
    // Try to detect which ecommerce model is being used (GA4 or UA)
    
    // GA4 items format
    if (ecom.items && Array.isArray(ecom.items) && ecom.items.length > 0) {
      var item = ecom.items[0];
      result.push("items[" + ecom.items.length + "]");
      
      if (item.item_name) result.push("name:" + item.item_name);
      if (item.item_id) result.push("id:" + item.item_id);
      if (item.price) result.push("$" + item.price);
    }
    
    // UA Enhanced Ecommerce format
    if (ecom.detail && ecom.detail.products) {
      var product = ecom.detail.products[0];
      result.push("detail");
      if (product.name) result.push("name:" + product.name);
      if (product.id) result.push("id:" + product.id);
      if (product.price) result.push("$" + product.price);
    }
    
    if (ecom.add && ecom.add.products) {
      result.push("add_to_cart");
      var product = ecom.add.products[0];
      if (product.name) result.push("name:" + product.name);
    }
    
    if (ecom.checkout) {
      result.push("checkout");
    }
    
    if (ecom.purchase) {
      result.push("purchase");
      if (ecom.purchase.actionField && ecom.purchase.actionField.revenue) {
        result.push("$" + ecom.purchase.actionField.revenue);
      }
    }
    
    // If we detected something specific
    if (result.length > 0) {
      return result.join(", ");
    }
    
    // Otherwise just return that ecommerce data exists
    return "yes";
  }
  
  // Function to log an event to Google Sheet
  function logToSheet(eventData) {
    try {
      // Extract key information
      var eventName = (eventData.event || 'unknown').toString();
      var page = window.location.pathname;
      var time = new Date().toLocaleTimeString();
      
      // Get enhanced ecommerce data
      var ecommerce = extractEcommerceData(eventData);
      
      // Additional useful data to extract
      var additionalData = "";
      
      // Look for common GTM variables that might be interesting
      if (eventData.gtm) additionalData += "GTM:" + eventData.gtm.uniqueEventId + " ";
      if (eventData.pageType) additionalData += "pageType:" + eventData.pageType + " ";
      if (eventData.userId) additionalData += "user:" + eventData.userId + " ";
      if (eventData.virtualPageURL) additionalData += "vPage:" + eventData.virtualPageURL + " ";
      
      // Add additional data to ecommerce string if available
      if (additionalData.length > 0) {
        ecommerce = ecommerce + " | " + additionalData.trim();
      }
      
      // Log to console with more details
      console.log('📊 GTM Event:', eventName, eventData, "Ecommerce:", ecommerce);
      
      // Send to Google Sheet via image request
      var img = new Image();
      img.src = SHEET_URL + 
                '?time=' + encodeURIComponent(time) + 
                '&page=' + encodeURIComponent(page) + 
                '&event=' + encodeURIComponent(eventName) + 
                '&ecommerce=' + encodeURIComponent(ecommerce);
                
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
