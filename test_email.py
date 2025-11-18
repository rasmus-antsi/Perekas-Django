#!/usr/bin/env python
"""
Simple script to test email configuration.
Run with: python test_email.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_core.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email():
    """Send a test email"""
    print("=" * 50)
    print("Testing Email Configuration")
    print("=" * 50)
    print(f"Backend: {settings.EMAIL_BACKEND}")
    print(f"Host: {settings.EMAIL_HOST}")
    print(f"Port: {settings.EMAIL_PORT}")
    print(f"From: {settings.DEFAULT_FROM_EMAIL}")
    print(f"User: {settings.EMAIL_HOST_USER}")
    print(f"Use SSL: {settings.EMAIL_USE_SSL}")
    print("=" * 50)
    
    # Get recipient email from command line or use default
    import sys
    if len(sys.argv) > 1:
        recipient = sys.argv[1]
    else:
        recipient = "info@perekas.ee"
    
    print(f"\nSending test email to: {recipient}")
    
    try:
        send_mail(
            subject='Perekas - Test Email',
            message='See on test e-kiri Perekas e-posti seadistuse kontrollimiseks.\n\nKui sa selle kirja näed, siis e-posti seadistus töötab korralikult!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        print("✅ Email sent successfully!")
        print(f"Check your inbox at: {recipient}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        print("\nTroubleshooting:")
        print("1. Check if EMAIL_HOST_PASSWORD is set in .env file")
        print("2. Verify the email password is correct")
        print("3. Check if port 465 is accessible")
        print("4. For development, you can use console backend:")
        print("   EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend")

if __name__ == '__main__':
    test_email()

