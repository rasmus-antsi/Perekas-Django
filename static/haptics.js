/**
 * Haptic Feedback Utility
 * Provides tactile feedback for user interactions
 * Supports Web Vibration API with graceful fallback
 */
class HapticFeedback {
  static isSupported() {
    // Check for Vibration API support
    const hasVibrate = 'vibrate' in navigator;
    
    if (!hasVibrate) {
      return false;
    }
    
    // Additional check: some browsers might have vibrate but not actually support it
    // Opera on iOS might not support it properly
    const userAgent = navigator.userAgent || '';
    const isOpera = userAgent.includes('OPR') || userAgent.includes('Opera') || userAgent.includes('OPiOS');
    const isIOS = /iPad|iPhone|iPod/.test(userAgent) && !window.MSStream;
    
    // Opera on iOS might not support vibration properly - but we'll still try
    if (isOpera && isIOS) {
      console.debug('HapticFeedback: Opera on iOS detected - vibration may not be fully supported');
      // Still return true to attempt vibration, but it might not work
    }
    
    return hasVibrate;
  }

  static isDisabled() {
    // Check user preference from localStorage
    // Can be set in settings/preferences
    return localStorage.getItem('hapticsDisabled') === 'true';
  }

  static patterns = {
    // Light feedback - subtle interactions
    light: [30],
    tap: [50],
    
    // Success feedback - positive actions
    success: [100, 50, 100],
    successStrong: [150, 75, 150],
    
    // Error feedback - negative actions
    error: [200],
    errorDouble: [100, 50, 200],
    
    // Celebration feedback - achievements
    celebration: [50, 50, 50, 50, 50],
    celebrationStrong: [100, 50, 100, 50, 100, 50, 100],
    
    // Badge/achievement feedback
    badge: [100, 50, 100, 50, 100],
    
    // Level up feedback
    levelUp: [300],
    levelUpStrong: [200, 100, 200, 100, 200],
    
    // Streak feedback
    streak: [50, 50, 50, 50, 50],
    streakMilestone: [100, 50, 100, 50, 100],
    
    // Notification feedback
    notification: [100],
    notificationStrong: [150, 75, 150],
    
    // Button press feedback
    buttonPress: [30],
    buttonSuccess: [50],
    
    // Form feedback
    formSubmit: [100],
    formError: [150],
    
    // Navigation feedback
    navigation: [50],
    
    // Modal feedback
    modalOpen: [50],
    modalClose: [30],
    
    // Task completion
    taskComplete: [100, 50, 100],
    taskApprove: [150, 75, 150],
    
    // Reward feedback
    rewardClaim: [100, 50, 100, 50, 100],
    rewardUnlock: [150, 75, 150],
  };

  /**
   * Trigger haptic feedback with a specific pattern
   * @param {string|Array} pattern - Pattern name or custom pattern array
   */
  static trigger(pattern) {
    // Don't trigger if disabled or not supported
    if (this.isDisabled() || !this.isSupported()) {
      return;
    }

    // Check if user prefers reduced motion
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    let vibrationPattern;
    
    // If pattern is a string, look it up in patterns object
    if (typeof pattern === 'string') {
      vibrationPattern = this.patterns[pattern];
      if (!vibrationPattern) {
        console.warn(`Haptic pattern "${pattern}" not found, using default light tap`);
        vibrationPattern = this.patterns.light;
      }
    } else if (Array.isArray(pattern)) {
      // Custom pattern array
      vibrationPattern = pattern;
    } else {
      // Default to light tap
      vibrationPattern = this.patterns.light;
    }

    try {
      const result = navigator.vibrate(vibrationPattern);
      // Some browsers return false if vibration is not supported
      if (result === false) {
        console.debug('HapticFeedback: Vibration API returned false - may not be supported on this device/browser');
        // Try alternative: some browsers need a different approach
        // For Opera on iOS, we might need to use a longer pattern
        if (vibrationPattern.length === 1 && vibrationPattern[0] < 100) {
          // Try with a slightly longer vibration for better compatibility
          navigator.vibrate([100]);
        }
      } else {
        // Success - log for debugging (remove in production)
        console.debug('HapticFeedback: Vibration triggered successfully', vibrationPattern);
      }
    } catch (error) {
      // Silently fail if vibration is not supported or blocked
      console.debug('HapticFeedback: Vibration error:', error);
    }
  }
  
  /**
   * Test haptic feedback - useful for debugging
   * @returns {boolean} True if vibration was triggered
   */
  static test() {
    if (!this.isSupported()) {
      console.log('HapticFeedback: Not supported on this device/browser');
      return false;
    }
    if (this.isDisabled()) {
      console.log('HapticFeedback: Disabled by user');
      return false;
    }
    this.trigger('tap');
    console.log('HapticFeedback: Test vibration triggered');
    return true;
  }

  /**
   * Enable haptic feedback (remove disabled flag)
   */
  static enable() {
    localStorage.removeItem('hapticsDisabled');
  }

  /**
   * Disable haptic feedback
   */
  static disable() {
    localStorage.setItem('hapticsDisabled', 'true');
  }

  /**
   * Check if haptics are currently enabled
   */
  static isEnabled() {
    return this.isSupported() && !this.isDisabled();
  }
}

// Make it available globally
window.HapticFeedback = HapticFeedback;

