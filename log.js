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
  
  // Function to safely stringify objects (from the successful approach)
  function safeStringify(obj, maxLen) {
    if (maxLen === undefined) maxLen = 200;
    try {
      var str = JSON.stringify(obj);
      if (str.length > maxLen) {
        return str.substring(0, maxLen) + "...";
      }
      return str;
    } catch (e) {
      return "Error: " + e.message;
    }
  }
  
  // Extract ecommerce data using the successful approach
  function extractEcommerceDetails(ecom) {
    if (!ecom) return "no";
    
    try {
      var ecomStr = "EXTRACT: ";
      
      // For GA4
      if (ecom.items) {
        ecomStr += "GA4 | items[" + ecom.items.length + "]";
        
        // Add first item details if available
        if (ecom.items.length > 0) {
          var firstItem = ecom.items[0];
          
          // Extract specific properties instead of stringifying the whole object
          var itemDetails = [];
          if (firstItem.item_name) itemDetails.push("name:" + firstItem.item_name);
          if (firstItem.item_id) itemDetails.push("id:" + firstItem.item_id);
          if (firstItem.price) itemDetails.push("price:" + firstItem.price);
          if (firstItem.quantity) itemDetails.push("qty:" + firstItem.quantity);
          
          if (itemDetails.length > 0) {
            ecomStr += " | " + itemDetails.join(" | ");
          } else {
            ecomStr += " | item:" + safeStringify(firstItem, 80);
          }
        }
        
        // Add value if available
        if (ecom.value) {
          ecomStr += " | value:" + ecom.value;
        }
        
        // Add currency if available
        if (ecom.currency) {
          ecomStr += " | currency:" + ecom.currency;
        }
      } 
      // For UA Enhanced Ecommerce
      else if (ecom.detail || ecom.add || ecom.purchase) {
        ecomStr += "UA | ";
        
        if (ecom.detail) {
          ecomStr += "detail | ";
          if (ecom.detail.products && ecom.detail.products.length > 0) {
            var product = ecom.detail.products[0];
            var productDetails = [];
            if (product.name) productDetails.push("name:" + product.name);
            if (product.id) productDetails.push("id:" + product.id);
            if (product.price) productDetails.push("price:" + product.price);
            
            if (productDetails.length > 0) {
              ecomStr += productDetails.join(" | ");
            } else {
              ecomStr += "product:" + safeStringify(product, 80);
            }
          }
        }
        
        if (ecom.add) {
          ecomStr += "add_to_cart | ";
          if (ecom.add.products && ecom.add.products.length > 0) {
            var product = ecom.add.products[0];
            var productDetails = [];
            if (product.name) productDetails.push("name:" + product.name);
            if (product.id) productDetails.push("id:" + product.id);
            if (product.price) productDetails.push("price:" + product.price);
            if (product.quantity) productDetails.push("qty:" + product.quantity);
            
            if (productDetails.length > 0) {
              ecomStr += productDetails.join(" | ");
            } else {
              ecomStr += "product:" + safeStringify(product, 80);
            }
          }
        }
        
        if (ecom.purchase) {
          ecomStr += "purchase | ";
          if (ecom.purchase.actionField) {
            var af = ecom.purchase.actionField;
            var afDetails = [];
            if (af.id) afDetails.push("id:" + af.id);
            if (af.revenue) afDetails.push("revenue:" + af.revenue);
            if (af.tax) afDetails.push("tax:" + af.tax);
            if (af.shipping) afDetails.push("shipping:" + af.shipping);
            
            if (afDetails.length > 0) {
              ecomStr += afDetails.join(" | ");
            } else {
              ecomStr += "transaction:" + safeStringify(af, 80);
            }
          }
          
          if (ecom.purchase.products && ecom.purchase.products.length > 0) {
            ecomStr += " | products:" + ecom.purchase.products.length;
          }
        }
      } 
      // If we couldn't identify the format
      else {
        // Just dump the first 150 chars of the stringified object
        ecomStr += "UNKNOWN_FORMAT | raw:" + safeStringify(ecom, 150);
      }
      
      return ecomStr;
    } catch (e) {
      return "ERROR: " + e.message;
    }
  }
  
  // Function to log an event to Google Sheet
  function logToSheet(eventData) {
    try {
      // Extract key information
      var eventName = (eventData.event || 'unknown').toString();
      var page = window.location.pathname;
      var time = new Date().toLocaleTimeString();
      
      // Get detailed ecommerce information using our successful method
      var ecommerceDetails = eventData.ecommerce ? 
                           extractEcommerceDetails(eventData.ecommerce) : 
                           "no";
      
      // Log to console
      console.log('📊 GTM Event:', eventName, eventData);
      console.log('   Ecommerce Details:', ecommerceDetails);
      
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
    
    // Also capture existing ecommerce events when first enabled
    if (isLoggingEnabled()) {
      console.log('Scanning existing dataLayer events...');
      
      // Find events with ecommerce data
      var ecommerceEvents = window.dataLayer.filter(function(item) {
        return item && typeof item === 'object' && item.ecommerce;
      });
      
      // Log them
      ecommerceEvents.forEach(function(event) {
        logToSheet(event);
      });
      
      console.log('Found and logged ' + ecommerceEvents.length + ' existing ecommerce events');
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
