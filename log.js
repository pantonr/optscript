// Complete GTM Event Logger with Full Data Extraction
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
  
  // Safe stringify function that handles circular references
  function safeStringify(obj, maxLength) {
    if (maxLength === undefined) maxLength = 500;
    
    try {
      // Handle different types
      if (obj === null) return "null";
      if (obj === undefined) return "undefined";
      if (typeof obj === "string") return obj.substring(0, maxLength);
      
      // For Date objects
      if (obj instanceof Date) return obj.toISOString();
      
      // For Arrays, convert each item
      if (Array.isArray(obj)) {
        if (obj.length === 0) return "[]";
        return "[" + obj.length + " items]";
      }
      
      // For objects, try to extract key information
      if (typeof obj === "object") {
        var seen = [];
        
        // Custom replacer function to handle circular references
        var str = JSON.stringify(obj, function(key, value) {
          if (typeof value === "object" && value !== null) {
            if (seen.includes(value)) return "[Circular]";
            seen.push(value);
          }
          return value;
        });
        
        if (str.length > maxLength) {
          return str.substring(0, maxLength) + "...";
        }
        return str;
      }
      
      // For other types, convert to string
      return String(obj);
    } catch (e) {
      return "Error stringifying: " + e.message;
    }
  }
  
  // Extract useful information from ecommerce object
  function extractEcommerceDetails(ecom) {
    if (!ecom) return "";
    
    var details = [];
    
    // Try to detect GA4 or UA format
    
    // GA4 format
    if (ecom.items && Array.isArray(ecom.items)) {
      var itemsList = [];
      ecom.items.forEach(function(item, index) {
        var itemInfo = [];
        if (item.item_name) itemInfo.push("name:" + item.item_name);
        if (item.item_id) itemInfo.push("id:" + item.item_id);
        if (item.price) itemInfo.push("$" + item.price);
        if (item.quantity) itemInfo.push("qty:" + item.quantity);
        
        itemsList.push((index + 1) + ":{" + itemInfo.join(",") + "}");
      });
      
      if (itemsList.length > 0) {
        details.push("items:[" + itemsList.join(" | ") + "]");
      }
      
      // Value
      if (ecom.value) details.push("value:" + ecom.value);
      
      // Currency
      if (ecom.currency) details.push("currency:" + ecom.currency);
    }
    
    // UA Enhanced Ecommerce format
    var actionTypes = ["detail", "click", "add", "remove", "checkout", "purchase"];
    actionTypes.forEach(function(action) {
      if (ecom[action]) {
        details.push("action:" + action);
        
        if (ecom[action].products && Array.isArray(ecom[action].products)) {
          var productList = [];
          ecom[action].products.forEach(function(product, index) {
            var productInfo = [];
            if (product.name) productInfo.push("name:" + product.name);
            if (product.id) productInfo.push("id:" + product.id);
            if (product.price) productInfo.push("$" + product.price);
            if (product.quantity) productInfo.push("qty:" + product.quantity);
            
            productList.push((index + 1) + ":{" + productInfo.join(",") + "}");
          });
          
          if (productList.length > 0) {
            details.push("products:[" + productList.join(" | ") + "]");
          }
        }
        
        if (ecom[action].actionField) {
          var actionFieldInfo = [];
          var af = ecom[action].actionField;
          if (af.id) actionFieldInfo.push("id:" + af.id);
          if (af.revenue) actionFieldInfo.push("revenue:" + af.revenue);
          if (af.step) actionFieldInfo.push("step:" + af.step);
          
          if (actionFieldInfo.length > 0) {
            details.push("actionField:{" + actionFieldInfo.join(",") + "}");
          }
        }
      }
    });
    
    // If we couldn't extract specific details
    if (details.length === 0) {
      return safeStringify(ecom, 200);
    }
    
    return details.join(" | ");
  }
  
  // Extract ALL relevant data from an event
  function extractEventData(eventData) {
    try {
      var result = {};
      
      // Copy all direct properties except ecommerce (which we'll handle specially)
      for (var prop in eventData) {
        if (prop !== 'ecommerce') {
          result[prop] = safeStringify(eventData[prop], 100);
        }
      }
      
      // Handle ecommerce data with special extraction
      if (eventData.ecommerce) {
        result.ecommerceDetails = extractEcommerceDetails(eventData.ecommerce);
      }
      
      return result;
    } catch (e) {
      return { error: "Error extracting data: " + e.message };
    }
  }
  
  // Format extracted data for Google Sheet
  function formatDataForSheet(extractedData) {
    try {
      var result = [];
      
      // Add ecommerce details if available
      if (extractedData.ecommerceDetails) {
        result.push("ECOM: " + extractedData.ecommerceDetails);
        delete extractedData.ecommerceDetails;
      }
      
      // Add other properties
      for (var prop in extractedData) {
        // Skip the event name since we already log it separately
        if (prop !== 'event') {
          result.push(prop + ": " + extractedData[prop]);
        }
      }
      
      return result.join(" | ");
    } catch (e) {
      return "Error formatting: " + e.message;
    }
  }
  
  // Function to log an event to Google Sheet
  function logToSheet(eventData) {
    try {
      // Extract key information
      var eventName = (eventData.event || 'unknown').toString();
      var page = window.location.pathname;
      var time = new Date().toLocaleTimeString();
      
      // Extract and format ALL available data
      var extractedData = extractEventData(eventData);
      var detailedData = formatDataForSheet(extractedData);
      
      // Log to console with more details
      console.log('📊 GTM Event:', eventName, eventData);
      console.log('📋 Extracted:', detailedData);
      
      // Send to Google Sheet via image request
      var img = new Image();
      img.src = SHEET_URL + 
                '?time=' + encodeURIComponent(time) + 
                '&page=' + encodeURIComponent(page) + 
                '&event=' + encodeURIComponent(eventName) + 
                '&ecommerce=' + encodeURIComponent(detailedData);
                
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
