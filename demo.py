#!/usr/bin/env python3
"""
Conversion Engine Demo Script
Demonstrates the full lead conversion pipeline from enrichment to booking.
"""

import asyncio
import json
import time
from datetime import datetime
import httpx

# Your deployed Render URL
BASE_URL = "https://conversion-engine-2nti.onrender.com"

class ConversionEngineDemo:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.prospect_id = None
        
    async def demo_health_check(self):
        """Test 1: Health Check - Verify the system is running"""
        print("🏥 DEMO 1: Health Check")
        print("=" * 50)
        
        try:
            response = await self.client.get(f"{BASE_URL}/health")
            health_data = response.json()
            
            print(f"✅ System Status: {health_data['status']}")
            print(f"🔒 Kill Switch: {health_data['kill_switch']}")
            print(f"🔴 Live Mode: {health_data['live_mode']}")
            print(f"🔗 HubSpot: {health_data['hubspot']}")
            print(f"⏰ Timestamp: {health_data['timestamp']}")
            print()
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
        return True

    async def demo_enrichment(self):
        """Test 2: Prospect Enrichment - Full signal collection"""
        print("🔍 DEMO 2: Prospect Enrichment Pipeline")
        print("=" * 50)
        
        # Demo prospect - a fictional AI startup
        prospect_data = {
            "company_name": "TechFlow AI",
            "contact_name": "Sarah Chen",
            "contact_email": "sarah@techflow.ai",
            "contact_phone": "+1-555-0123",
            "contact_title": "CTO"
        }
        
        print(f"📋 Enriching prospect: {prospect_data['company_name']}")
        print(f"👤 Contact: {prospect_data['contact_name']} ({prospect_data['contact_title']})")
        
        try:
            response = await self.client.post(f"{BASE_URL}/prospects/enrich", json=prospect_data)
            enrichment_result = response.json()
            
            self.prospect_id = enrichment_result['prospect_id']
            
            print(f"✅ Prospect ID: {self.prospect_id}")
            print(f"🎯 Segment: {enrichment_result['segment']}")
            print(f"📊 Confidence: {enrichment_result['confidence']:.2f}")
            print(f"🤖 AI Maturity Score: {enrichment_result.get('ai_maturity', 'N/A')}")
            print(f"📈 Bench Match: {enrichment_result.get('bench_match', 'N/A')}")
            print(f"📊 Hiring Velocity: {enrichment_result.get('hiring_velocity', 'N/A')}")
            print(f"⚠️  Honesty Flags: {enrichment_result.get('honesty_flags', [])}")
            hubspot = enrichment_result.get('hubspot', {})
            print(f"🏢 HubSpot Sync: {hubspot.get('status', 'N/A') if isinstance(hubspot, dict) else hubspot}")
            print()
            
        except Exception as e:
            print(f"❌ Enrichment failed: {e}")
            return False
        return True

    async def demo_outreach(self):
        """Test 3: Automated Outreach - Email composition and sending"""
        print("📧 DEMO 3: Automated Outreach")
        print("=" * 50)
        
        if not self.prospect_id:
            print("❌ No prospect ID available")
            return False
            
        try:
            response = await self.client.post(f"{BASE_URL}/prospects/{self.prospect_id}/outreach")
            if response.status_code == 400:
                err = response.json()
                print(f"⚠️  State conflict: {err.get('detail', 'unknown')}")
                print("   Resetting: creating a fresh prospect for outreach...")
                # Create a fresh prospect just for outreach
                fresh = await self.client.post(f"{BASE_URL}/prospects/enrich", json={
                    "company_name": "OutreachTest Corp",
                    "contact_name": "Alex Demo",
                    "contact_email": "alex@outreachtest.com",
                    "contact_title": "VP Engineering",
                })
                fresh_data = fresh.json()
                fresh_id = fresh_data["prospect_id"]
                response = await self.client.post(f"{BASE_URL}/prospects/{fresh_id}/outreach")
            
            outreach_result = response.json()
            if response.status_code >= 400:
                print(f"❌ Outreach error: {outreach_result.get('detail', outreach_result)}")
                return False
            
            print(f"✅ Email Status: {outreach_result['status']}")
            print(f"📬 Subject: {outreach_result['email_subject']}")
            print(f"🎯 Confidence Level: {outreach_result.get('confidence_level', 'N/A')}")
            print(f"📊 Signal References: {len(outreach_result.get('signal_references', []))}")
            print(f"🔤 Tokens Used: {outreach_result.get('tokens_used', 'N/A')}")
            print()
            
        except Exception as e:
            print(f"❌ Outreach failed: {e}")
            return False
        return True

    async def demo_conversation(self):
        """Test 4: Conversation Management - Handle prospect reply"""
        print("💬 DEMO 4: Conversation Management")
        print("=" * 50)
        
        if not self.prospect_id:
            print("❌ No prospect ID available")
            return False
            
        # Simulate a positive prospect reply
        reply_data = {
            "prospect_id": self.prospect_id,
            "message": "Hi! This sounds interesting. I'd like to learn more about how you can help us with our AI implementation. Can we schedule a call?",
            "channel": "email"
        }
        
        print(f"📨 Simulating prospect reply: '{reply_data['message'][:50]}...'")
        
        try:
            response = await self.client.post(f"{BASE_URL}/prospects/{self.prospect_id}/reply", json=reply_data)
            conversation_result = response.json()
            
            if response.status_code >= 400:
                print(f"❌ Reply error: {conversation_result.get('detail', conversation_result)}")
                return False
            
            print(f"✅ Reply processed successfully")
            print(f"🤖 Agent Response: '{conversation_result['reply'][:100]}...'")
            print(f"📊 New State: {conversation_result['state']}")
            print(f"🏷️  Reply Class: {conversation_result.get('reply_class', 'N/A')}")
            print(f"📞 Should Book Call: {conversation_result['should_book_call']}")
            print(f"👤 Needs Human Handoff: {conversation_result['needs_human_handoff']}")
            print()
            
        except Exception as e:
            print(f"❌ Conversation handling failed: {e}")
            return False
        return True

    async def demo_prospect_details(self):
        """Test 5: Prospect Details - View complete prospect profile"""
        print("👤 DEMO 5: Prospect Profile")
        print("=" * 50)
        
        if not self.prospect_id:
            print("❌ No prospect ID available")
            return False
            
        try:
            response = await self.client.get(f"{BASE_URL}/prospects/{self.prospect_id}")
            prospect_details = response.json()
            
            print(f"🆔 ID: {prospect_details['id']}")
            print(f"🏢 Company: {prospect_details['company_name']}")
            print(f"👤 Contact: {prospect_details['contact_name']} ({prospect_details.get('contact_title', 'N/A')})")
            print(f"📧 Email: {prospect_details.get('contact_email', 'N/A')}")
            print(f"📱 Phone: {prospect_details.get('contact_phone', 'N/A')}")
            print(f"📊 State: {prospect_details['state']}")
            print(f"📬 Emails Sent: {prospect_details['emails_sent']}")
            print(f"🕒 Last Contact: {prospect_details.get('last_contact', 'N/A')}")
            print()
            
        except Exception as e:
            print(f"❌ Failed to get prospect details: {e}")
            return False
        return True

    async def demo_webhook_endpoints(self):
        """Test 6: Webhook Endpoints - Verify webhook receivers are working"""
        print("🔗 DEMO 6: Webhook Endpoints")
        print("=" * 50)
        
        all_ok = True

        # Test email webhook
        email_webhook_data = {
            "type": "email.delivered",
            "data": {
                "email_id": "test-email-123",
                "to": "sarah@techflow.ai",
                "subject": "Test Email"
            }
        }
        
        try:
            response = await self.client.post(f"{BASE_URL}/webhooks/email/reply", json=email_webhook_data)
            print(f"✅ Email Webhook: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"❌ Email webhook test failed: {e}")
            all_ok = False
        
        # Test SMS webhook
        sms_webhook_data = {
            "from": "+1-555-0123",
            "text": "Yes, I'm interested in learning more",
            "to": "4571"
        }
        
        try:
            response = await self.client.post(f"{BASE_URL}/webhooks/sms/inbound", json=sms_webhook_data)
            print(f"✅ SMS Webhook: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"❌ SMS webhook test failed: {e}")
            all_ok = False
        
        print()
        return all_ok

    async def demo_prospects_list(self):
        """Test 7: List All Prospects"""
        print("📋 DEMO 7: All Prospects")
        print("=" * 50)
        
        try:
            response = await self.client.get(f"{BASE_URL}/prospects")
            prospects_list = response.json()
            
            print(f"📊 Total Prospects: {len(prospects_list)}")
            for prospect in prospects_list:
                print(f"  🆔 {prospect['id']} | 🏢 {prospect['company']} | 🎯 {prospect['segment']} | 📊 {prospect['state']} | 📬 {prospect['emails_sent']} emails")
            print()
            
        except Exception as e:
            print(f"❌ Failed to list prospects: {e}")
            return False
        return True

    async def run_full_demo(self):
        """Run the complete demo sequence"""
        print("🚀 CONVERSION ENGINE DEMO")
        print("=" * 60)
        print(f"🌐 Base URL: {BASE_URL}")
        print(f"⏰ Demo Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print()
        
        # Run all demo steps
        steps = [
            ("Health Check", self.demo_health_check),
            ("Prospect Enrichment", self.demo_enrichment),
            ("Automated Outreach", self.demo_outreach),
            ("Webhook Endpoints", self.demo_webhook_endpoints),
            ("Conversation Management", self.demo_conversation),
            ("Prospect Profile", self.demo_prospect_details),
            ("Prospects List", self.demo_prospects_list),
        ]
        
        results = []
        for step_name, step_func in steps:
            print(f"⏳ Running: {step_name}...")
            start_time = time.time()
            
            try:
                success = await step_func()
                duration = time.time() - start_time
                results.append((step_name, success, duration))
                
                if success:
                    print(f"✅ {step_name} completed in {duration:.2f}s")
                else:
                    print(f"❌ {step_name} failed after {duration:.2f}s")
                    
            except Exception as e:
                duration = time.time() - start_time
                results.append((step_name, False, duration))
                print(f"💥 {step_name} crashed: {e}")
            
            print("-" * 50)
            time.sleep(1)  # Brief pause between steps
        
        # Summary
        print("📊 DEMO SUMMARY")
        print("=" * 60)
        successful = sum(1 for _, success, _ in results if success)
        total = len(results)
        
        for step_name, success, duration in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} | {step_name:<25} | {duration:.2f}s")
        
        print("-" * 60)
        print(f"🎯 Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
        print(f"⏰ Total Duration: {sum(duration for _, _, duration in results):.2f}s")
        print("=" * 60)
        
        await self.client.aclose()

async def main():
    """Run the demo"""
    demo = ConversionEngineDemo()
    await demo.run_full_demo()

if __name__ == "__main__":
    asyncio.run(main())