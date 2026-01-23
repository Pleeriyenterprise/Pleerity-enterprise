/**
 * Tawk.to Live Chat Integration
 * 
 * This component loads the Tawk.to widget script and provides
 * API access for integration with the Pleerity support chatbot.
 * 
 * Features:
 * - Lazy loading of Tawk.to widget
 * - API methods for showing/hiding widget
 * - Metadata passing for conversation context
 * 
 * To configure:
 * 1. Create a Tawk.to account at https://www.tawk.to
 * 2. Get your Property ID and Widget ID from Dashboard > Administration > Channels > Chat Widget
 * 3. Set REACT_APP_TAWKTO_PROPERTY_ID and REACT_APP_TAWKTO_WIDGET_ID in .env
 */
import { useEffect } from 'react';

// Tawk.to configuration
// These should be set in your .env file
const TAWKTO_PROPERTY_ID = process.env.REACT_APP_TAWKTO_PROPERTY_ID || 'YOUR_PROPERTY_ID';
const TAWKTO_WIDGET_ID = process.env.REACT_APP_TAWKTO_WIDGET_ID || 'YOUR_WIDGET_ID';

export default function TawkToWidget() {
  useEffect(() => {
    // Don't load if IDs not configured
    if (TAWKTO_PROPERTY_ID === 'YOUR_PROPERTY_ID') {
      console.log('Tawk.to not configured. Set REACT_APP_TAWKTO_PROPERTY_ID in .env');
      return;
    }

    // Create Tawk.to API object
    window.Tawk_API = window.Tawk_API || {};
    window.Tawk_LoadStart = new Date();

    // Load Tawk.to script
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://embed.tawk.to/${TAWKTO_PROPERTY_ID}/${TAWKTO_WIDGET_ID}`;
    script.charset = 'UTF-8';
    script.setAttribute('crossorigin', '*');
    
    document.head.appendChild(script);

    // Configure Tawk.to when loaded
    window.Tawk_API.onLoad = function() {
      console.log('Tawk.to loaded');
      
      // Hide widget by default (our chatbot is primary)
      window.Tawk_API.hideWidget();
    };

    // Cleanup
    return () => {
      // Remove script if component unmounts
      const existingScript = document.querySelector(`script[src*="tawk.to"]`);
      if (existingScript) {
        existingScript.remove();
      }
    };
  }, []);

  return null; // This component doesn't render anything
}

/**
 * Helper functions for Tawk.to API
 * Can be called from other components
 */
export const TawkToAPI = {
  /**
   * Show the Tawk.to widget
   */
  show: () => {
    if (window.Tawk_API && window.Tawk_API.showWidget) {
      window.Tawk_API.showWidget();
    }
  },

  /**
   * Hide the Tawk.to widget
   */
  hide: () => {
    if (window.Tawk_API && window.Tawk_API.hideWidget) {
      window.Tawk_API.hideWidget();
    }
  },

  /**
   * Maximize (open) the chat window
   */
  maximize: () => {
    if (window.Tawk_API && window.Tawk_API.maximize) {
      window.Tawk_API.maximize();
    }
  },

  /**
   * Minimize the chat window
   */
  minimize: () => {
    if (window.Tawk_API && window.Tawk_API.minimize) {
      window.Tawk_API.minimize();
    }
  },

  /**
   * Set visitor attributes for context
   * @param {Object} attributes - Visitor data
   */
  setAttributes: (attributes) => {
    if (window.Tawk_API && window.Tawk_API.setAttributes) {
      window.Tawk_API.setAttributes(attributes, function(error) {
        if (error) {
          console.error('Tawk.to setAttributes error:', error);
        }
      });
    }
  },

  /**
   * Add custom event/tag
   * @param {string} tag - Tag name
   * @param {Object} data - Additional data
   */
  addTags: (tags) => {
    if (window.Tawk_API && window.Tawk_API.addTags) {
      window.Tawk_API.addTags(tags, function(error) {
        if (error) {
          console.error('Tawk.to addTags error:', error);
        }
      });
    }
  },

  /**
   * Check if Tawk.to is loaded
   */
  isLoaded: () => {
    return !!(window.Tawk_API && window.Tawk_API.maximize);
  },

  /**
   * Open chat with conversation context from our AI chatbot
   * @param {Object} context - Conversation context
   */
  openWithContext: (context) => {
    if (window.Tawk_API) {
      // Set attributes for agent context
      TawkToAPI.setAttributes({
        'conversation_id': context.conversationId || '',
        'crn': context.crn || '',
        'service_area': context.serviceArea || '',
        'category': context.category || '',
        'source': 'pleerity_ai_chatbot',
        'transcript_available': 'yes',
      });

      // Add tags for routing
      if (context.category) {
        TawkToAPI.addTags([context.category]);
      }
      if (context.serviceArea) {
        TawkToAPI.addTags([context.serviceArea]);
      }

      // Show and maximize
      TawkToAPI.show();
      TawkToAPI.maximize();
    }
  },
};
