#!/usr/bin/env python3
"""
View Demo Content - Shows actual emails and conversations from your demo
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "https://conversion-engine-2nti.onrender.com"

async def view_demo_content():
    """Fetch and display the actual demo content"""
    client = httpx.AsyncClient(timeout=30.0)
    
    print("📧 ACTUAL DEMO CONTENT VIEWER")
    print("=" * 60)
    print(f"🌐 Fetching from: {BASE_URL}")
    print("=" * 60)
    
    try:
        # Get all prospects from your demo
        print("📋 Fetching all prospects...")
        response = await client.get(f"{BASE_URL}/prospects")
        prospects = response.json()
        
        print(f"📊 Found {len(prospects)} prospects from demo:")
        print()
        
        for prospect in prospects:
            print(f"🆔 PROSPECT: {prospect['id']}")
            print(f"🏢 Company: {prospect['company']}")
            print(f"🎯 Segment: {prospect['segment']}")
            print(f"📊 State: {prospect['state']}")
            print(f"📬 Emails Sent: {prospect['emails_sent']}")
            print("-" * 40)
            
            # Get detailed prospect info
            try:
                detail_response = await client.get(f"{BASE_URL}/prospects/{prospect['id']}")
                prospect_detail = detail_response.json()
                
                print(f"👤 Contact: {prospect_detail.get('contact_name', 'N/A')}")
                print(f"📧 Email: {prospect_detail.get('contact_email', 'N/A')}")
                print(f"📱 Phone: {prospect_detail.get('contact_phone', 'N/A')}")
                print(f"💼 Title: {prospect_detail.get('contact_title', 'N/A')}")
                print(f"🕒 Last Contact: {prospect_detail.get('last_contact', 'N/A')}")
                
                # Show classification if available
                if prospect_detail.get('classification'):
                    classification = prospect_detail['classification']
                    print(f"🎯 Classification:")
                    print(f"   Segment: {classification.get('segment', 'N/A')}")
                    print(f"   Confidence: {classification.get('confidence', 'N/A')}")
                    print(f"   Bench Match: {classification.get('bench_match', 'N/A')}")
                
                # Show signal brief if available
                if prospect_detail.get('signal_brief'):
                    brief = prospect_detail['signal_brief']
                    print(f"📊 Signal Brief:")
                    if brief.get('ai_maturity'):
                        ai_maturity = brief['ai_maturity']
                        print(f"   AI Maturity Score: {ai_maturity.get('score', 'N/A')}")
                        print(f"   AI Maturity Level: {ai_maturity.get('level', 'N/A')}")
                
            except Exception as e:
                print(f"   ⚠️ Could not fetch details: {e}")
            
            print("=" * 60)
        
        # Show sample email content (from local example)
        print("📧 SAMPLE EMAIL CONTENT (Local Example):")
        print("=" * 60)
        
        sample_email = {
            "subject": "Yellow.ai's AI Maturity Score of 0/3 — Exploring Growth Opportunities?",
            "body": """We noticed your current AI maturity score is 0/3 (confidence level 0.40). Are you exploring opportunities to strengthen your AI/ML capabilities as you scale?

Top quartile performers in your sector typically demonstrate measurable AI capabilities, maintain transparent tech stack documentation, and partner with enterprise software providers. We currently have ML/AI engineers available to help bridge these gaps.

Worth a 30-minute conversation to discuss how we can support your goals?"""
        }
        
        print(f"📬 Subject: {sample_email['subject']}")
        print(f"📝 Body:")
        print("   " + "="*50)
        for line in sample_email['body'].split('\n'):
            print(f"   {line}")
        print("   " + "="*50)
        
        print("\n💡 NOTE: Your demo emails from the Render deployment are stored")
        print("   on the Render server. To see them:")
        print("   1. Go to https://dashboard.render.com")
        print("   2. Select your 'conversion-engine-2nti' service")
        print("   3. Click 'Logs' tab")
        print("   4. Search for timestamps around your demo time")
        
    except Exception as e:
        print(f"❌ Error fetching demo content: {e}")
    
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(view_demo_content())