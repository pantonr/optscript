// GTM Event Logger with Minimal JSON Change
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
  
  // Function to log an event to Google Sheet
  function logToSheet(eventData) {
    try {
      // Extract key information
      var eventName = (eventData.event || 'unknown').toString();
      var page = window.location.pathname;
      var time = new Date().toLocaleTimeString();
      
      // ONLY CHANGE: Modify ecommerce data to include JSON instead of yes/no
      var ecommerce = "no";
      if (eventData.ecommerce) {
        try {
          ecommerce = "JSON:" + JSON.stringify(eventData.ecommerce).substring(0, 200);
        } catch(e) {
          ecommerce = "error:" + e.message;
        }
      }
      
      // Log to console
      console.log('📊 GTM Event:', eventName, eventData);
      
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
