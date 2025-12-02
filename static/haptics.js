/**
 * Haptic Feedback Utility
 * Provides tactile feedback for user interactions
 * Supports Web Vibration API with graceful fallback
 */
class HapticFeedback {
  static isSupported() {
    return 'vibrate' in navigator;
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
      navigator.vibrate(vibrationPattern);
    } catch (error) {
      // Silently fail if vibration is not supported or blocked
      console.debug('Haptic feedback not available:', error);
    }
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

