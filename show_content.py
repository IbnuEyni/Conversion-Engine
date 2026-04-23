#!/usr/bin/env python3
"""
Show Email & SMS Content from Demo
"""

import asyncio
import httpx

BASE_URL = "https://conversion-engine-2nti.onrender.com"

async def show_demo_content():
    """Show the actual email and SMS content generated"""
    client = httpx.AsyncClient(timeout=30.0)
    
    print("📧 DEMO EMAIL & SMS CONTENT")
    print("=" * 60)
    
    # Create a test prospect
    prospect_data = {
        "company_name": "Demo Corp",
        "contact_name": "John Demo",
        "contact_email": "john@democorp.com",
        "contact_phone": "+1-555-DEMO",
        "contact_title": "CEO"
    }
    
    try:
        # 1. Enrich prospect
        print("🔍 Step 1: Enriching prospect...")
        response = await client.post(f"{BASE_URL}/prospects/enrich", json=prospect_data)
        result = response.json()
        prospect_id = result['prospect_id']
        print(f"✅ Created prospect: {prospect_id}")
        
        # 2. Generate outreach email
        print("\n📧 Step 2: Generating outreach email...")
        response = await client.post(f"{BASE_URL}/prospects/{prospect_id}/outreach")
        outreach = response.json()
        
        print(f"📬 EMAIL SUBJECT:")
        print(f"   {outreach['email_subject']}")
        print(f"\n📝 EMAIL BODY:")
        print("   " + "="*50)
        
        # Get the full prospect details to see the email body
        response = await client.get(f"{BASE_URL}/prospects/{prospect_id}")
        prospect = response.json()
        
        print("   [Email body would be shown here - check Render logs for full content]")
        print("   " + "="*50)
        
        # 3. Simulate conversation
        print(f"\n💬 Step 3: Simulating conversation...")
        reply_data = {
            "prospect_id": prospect_id,
            "message": "Tell me more about your services",
            "channel": "email"
        }
        
        response = await client.post(f"{BASE_URL}/prospects/{prospect_id}/reply", json=reply_data)
        conversation = response.json()
        
        print(f"🤖 AGENT REPLY:")
        print(f"   {conversation['reply'][:200]}...")
        
        print(f"\n📊 DEMO SUMMARY:")
        print(f"   Prospect ID: {prospect_id}")
        print(f"   Email Subject: {outreach['email_subject']}")
        print(f"   Confidence: {outreach.get('confidence_level', 'N/A')}")
        print(f"   Signal References: {len(outreach.get('signal_references', []))}")
        print(f"   Conversation State: {conversation['state']}")
        print(f"   Should Book Call: {conversation['should_book_call']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(show_demo_content())