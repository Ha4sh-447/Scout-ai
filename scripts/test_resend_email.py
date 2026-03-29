#!/usr/bin/env python3
"""
Test script for sending emails via SMTP (Gmail, Outlook, custom servers)

Usage:
    python scripts/test_resend_email.py

Prerequisites:
    1. Configure EMAIL_SMTP_HOST, EMAIL_SENDER, EMAIL_PASSWORD in .env
    2. Ensure python-dotenv is installed

Example .env configurations:
    Gmail:
        EMAIL_SMTP_HOST=smtp.gmail.com
        EMAIL_SMTP_PORT=587
        EMAIL_SENDER=your-email@gmail.com
        EMAIL_PASSWORD=your_16_digit_app_password
    
    Outlook:
        EMAIL_SMTP_HOST=smtp.office365.com
        EMAIL_SMTP_PORT=587
        EMAIL_SENDER=your-email@outlook.com
        EMAIL_PASSWORD=your_outlook_password
"""

import sys
import os
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def send_test_email():
    """Send a test email via SMTP using smtplib"""
    
    # Get configuration from environment
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("EMAIL_SMTP_HOST")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    
    # Validate configuration
    if not sender_email or not sender_password or not smtp_host:
        print("❌ ERROR: Required email variables not set in .env")
        print("   Missing: EMAIL_SENDER, EMAIL_PASSWORD, or EMAIL_SMTP_HOST")
        print("\n   Configure in .env:")
        print("     EMAIL_SMTP_HOST=smtp.gmail.com  (or smtp.office365.com, etc)")
        print("     EMAIL_SENDER=your-email@example.com")
        print("     EMAIL_PASSWORD=your_app_password")
        return False
    
    # Use sender email as recipient if not specified
    recipient_email = sender_email
    
    print(f"📧 Sending test email via SMTP...")
    print(f"   SMTP Host: {smtp_host}:{smtp_port}")
    print(f"   From: {sender_email}")
    print(f"   To: {recipient_email}")
    
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🎉 Scout AI - Email Configuration Test"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        
        # Create HTML email body
        html_content = f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #2563eb; color: white; padding: 20px; border-radius: 8px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; margin-top: 20px; }}
                    .footer {{ margin-top: 20px; text-align: center; color: #666; font-size: 12px; }}
                    .config-item {{ background: white; padding: 10px; margin: 5px 0; border-left: 3px solid #2563eb; }}
                    .success {{ color: #10b981; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ SMTP Email Configuration Working</h1>
                    </div>
                    <div class="content">
                        <p>Hello! 👋</p>
                        <p>This is a <span class="success">test email from Scout AI</span> - your SMTP email system is working!</p>
                        <p><strong>Configuration Details:</strong></p>
                        <div class="config-item">
                            <strong>SMTP Host:</strong> {smtp_host}:{smtp_port}
                        </div>
                        <div class="config-item">
                            <strong>Sender:</strong> {sender_email}
                        </div>
                        <div class="config-item">
                            <strong>Status:</strong> <span class="success">✅ Connected & Authenticated</span>
                        </div>
                        <p style="margin-top: 20px;">Your email system is now configured and ready to send job digests and notifications! 🚀</p>
                    </div>
                    <div class="footer">
                        <p>Scout AI - Agentic Job Finder</p>
                        <p>© 2026 All rights reserved</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Attach HTML content
        part = MIMEText(html_content, "html")
        msg.attach(part)
        
        # Connect to SMTP server
        print(f"   Connecting to {smtp_host}:{smtp_port}...")
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.set_debuglevel(0)  # Set to 1 for verbose debugging
        
        # Start TLS encryption
        print(f"   Starting TLS encryption...")
        server.starttls()
        
        # Login with credentials
        print(f"   Authenticating...")
        server.login(sender_email, sender_password)
        
        # Send email
        print(f"   Sending email...")
        server.sendmail(sender_email, recipient_email, msg.as_string())
        
        # Close connection
        server.quit()
        
        print(f"\n✅ Test email sent successfully!")
        print(f"   Check your inbox at: {recipient_email}")
        print(f"\n   Your SMTP email configuration is ready to use! 🎉")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ Authentication failed: {str(e)}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Verify EMAIL_SENDER and EMAIL_PASSWORD in .env")
        print(f"   2. Gmail users: Use 16-digit App Password (not regular password)")
        print(f"   3. Outlook users: Ensure Office 365 account is active")
        print(f"   4. Check if two-factor authentication is enabled")
        return False
    except smtplib.SMTPException as e:
        error_str = str(e)
        print(f"\n❌ SMTP connection error: {error_str}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Verify EMAIL_SMTP_HOST is correct")
        print(f"   2. Check EMAIL_SMTP_PORT (usually 587 for TLS)")
        print(f"   3. Check network/firewall allows outgoing SMTP")
        print(f"   4. Try a different SMTP port (465 for SSL)")
        return False
    except Exception as e:
        print(f"\n❌ Failed to send email: {str(e)}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Verify all email variables are set in .env")
        print(f"   2. Check internet connection to SMTP server")
        print(f"   3. Ensure email account is active and not locked")
        print(f"   4. Check email provider's security settings")
        return False

if __name__ == "__main__":
    success = send_test_email()
    sys.exit(0 if success else 1)
