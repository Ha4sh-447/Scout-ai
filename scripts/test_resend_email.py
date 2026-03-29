#!/usr/bin/env python3
"""
Test script for sending emails via Resend SMTP

Usage:
    python scripts/test_resend_email.py

Prerequisites:
    1. Set EMAIL_PASSWORD in .env with your Resend API key
    2. Ensure python-dotenv is installed
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
    """Send a test email via Resend SMTP using smtplib"""
    
    # Get configuration from environment
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.resend.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    recipient_email = os.getenv("EMAIL_RECIPIENT", "harshsaindane1711@gmail.com")
    
    # Validate configuration
    if not sender_email or not sender_password:
        print("❌ ERROR: EMAIL_SENDER or EMAIL_PASSWORD not set in .env")
        print("   Please configure your Resend SMTP credentials")
        return False
    
    if sender_password == "re_your_resend_api_key_here_replace_with_actual":
        print("❌ ERROR: EMAIL_PASSWORD is still a placeholder")
        print("   Please replace it with your actual Resend API key in .env")
        print("   Get your key from: https://resend.com/api-keys")
        return False
    
    print(f"📧 Sending test email via Resend SMTP...")
    print(f"   From: {sender_email}")
    print(f"   To: {recipient_email}")
    print(f"   SMTP Host: {smtp_host}:{smtp_port}")
    
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🎉 Scout AI - Email Test Success"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        
        # Create HTML email body
        html_content = """
        <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background-color: #4CAF50; color: white; padding: 20px; border-radius: 5px; text-align: center; }
                    .content { padding: 20px; background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; margin-top: 20px; }
                    .footer { margin-top: 20px; text-align: center; color: #666; font-size: 12px; }
                    .success { color: #4CAF50; font-weight: bold; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ Email Configuration Test</h1>
                    </div>
                    <div class="content">
                        <p>Hello! 👋</p>
                        <p>This is a <span class="success">test email from Scout AI</span> using <strong>Resend SMTP</strong>.</p>
                        <p><strong>Configuration Details:</strong></p>
                        <ul>
                            <li>Service: Resend</li>
                            <li>SMTP Host: smtp.resend.com</li>
                            <li>From: onboarding@resend.com</li>
                            <li>Status: ✅ Working</li>
                        </ul>
                        <p>Your email system is now configured and ready to send job digests and notifications! 🚀</p>
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
        
        # Connect to Resend SMTP with explicit STARTTLS
        print(f"   Connecting to {smtp_host}:{smtp_port}...")
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.set_debuglevel(0)  # Set to 1 for verbose debugging
        
        # Start TLS encryption
        print(f"   Starting TLS encryption...")
        server.starttls()
        
        # Login with credentials
        print(f"   Authenticating with Resend API key...")
        server.login("resend", sender_password)  # Resend uses 'resend' as username
        
        # Send email
        print(f"   Sending email...")
        server.sendmail(sender_email, recipient_email, msg.as_string())
        
        # Close connection
        server.quit()
        
        print(f"✅ Test email sent successfully!")
        print(f"   Check your inbox at: {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {str(e)}")
        print(f"\n   Issue: Invalid Resend API key")
        print(f"   Solution:")
        print(f"   1. Get a new API key from: https://resend.com/api-keys")
        print(f"   2. Update EMAIL_PASSWORD in .env with the key")
        print(f"   3. The key should start with 're_'")
        return False
    except smtplib.SMTPException as e:
        error_str = str(e)
        print(f"❌ SMTP error: {error_str}")
        print(f"\n   Troubleshooting:")
        
        if "not verified" in error_str.lower() or "domain" in error_str.lower():
            print(f"   ⚠️  Domain Not Verified Issue:")
            print(f"   The email domain needs to be verified in Resend dashboard")
            print(f"   Steps to fix:")
            print(f"   1. Go to https://resend.com/domains")
            print(f"   2. Add and verify your domain or use a Resend subdomain")
            print(f"   3. Use the verified email address in EMAIL_SENDER")
            print(f"   4. Note: 'scoutai@resend.com' requires domain verification")
            print(f"      Consider using Resend's default subdomain instead")
        else:
            print(f"   1. SMTP server blocked - check firewall/network")
            print(f"   2. Wrong port - Resend uses port 587 with STARTTLS")
            print(f"   3. Invalid credentials - double-check API key format")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Verify EMAIL_PASSWORD is set correctly in .env")
        print(f"   2. Check network connectivity to smtp.resend.com")
        print(f"   3. Ensure your Resend account is active")
        print(f"   4. Check spam folder for test email")
        return False

if __name__ == "__main__":
    success = send_test_email()
    sys.exit(0 if success else 1)
