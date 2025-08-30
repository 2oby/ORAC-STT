#!/usr/bin/env python3
"""Test script for ORAC STT heartbeat and ORAC Core connectivity."""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
import sys
import argparse


async def send_heartbeat(base_url: str, instance_id: str = "hey_orac_test_001"):
    """Send a test heartbeat to ORAC STT."""
    
    # Create test heartbeat data
    heartbeat_data = {
        "source": "hey_orac",
        "instance_id": instance_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "models": [
            {
                "topic": "jarvis",
                "wake_word": "Hey Jarvis",
                "status": "active",
                "last_triggered": (datetime.utcnow() - timedelta(minutes=2)).isoformat() + "Z",
                "trigger_count": 42
            },
            {
                "topic": "friday",
                "wake_word": "Hey Friday", 
                "status": "active",
                "last_triggered": (datetime.utcnow() - timedelta(minutes=10)).isoformat() + "Z",
                "trigger_count": 15
            },
            {
                "topic": "cortana",
                "wake_word": "Hey Cortana",
                "status": "inactive",  # This should be filtered out
                "last_triggered": None,
                "trigger_count": 0
            }
        ]
    }
    
    url = f"{base_url}/stt/v1/heartbeat"
    
    print(f"\n🔄 Sending heartbeat to {url}")
    print(f"📦 Payload: {json.dumps(heartbeat_data, indent=2)}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=heartbeat_data) as response:
                status = response.status
                result = await response.json()
                
                if status == 200:
                    print(f"✅ Heartbeat successful!")
                    print(f"📊 Response: {json.dumps(result, indent=2)}")
                else:
                    print(f"❌ Heartbeat failed with status {status}")
                    print(f"📊 Response: {json.dumps(result, indent=2)}")
                
                return status == 200
                
    except aiohttp.ClientError as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


async def check_heartbeat_status(base_url: str):
    """Check the heartbeat status endpoint."""
    
    url = f"{base_url}/stt/v1/heartbeat/status"
    
    print(f"\n📊 Checking heartbeat status at {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                status = response.status
                result = await response.json()
                
                if status == 200:
                    print(f"✅ Status check successful!")
                    print(f"📊 Current status:")
                    print(f"   - Instance count: {result.get('instance_count', 0)}")
                    print(f"   - Active topics: {result.get('total_active_topics', 0)}")
                    print(f"   - Inactive topics: {result.get('total_inactive_topics', 0)}")
                    
                    for instance in result.get('instances', []):
                        print(f"\n   Instance: {instance['instance_id']}")
                        print(f"     - Source: {instance['source']}")
                        print(f"     - Age: {instance['age_seconds']:.1f}s")
                        print(f"     - Stale: {instance['is_stale']}")
                        print(f"     - Active models: {instance['active_models']}")
                        print(f"     - Inactive models: {instance['inactive_models']}")
                else:
                    print(f"❌ Status check failed with status {status}")
                    print(f"📊 Response: {json.dumps(result, indent=2)}")
                
                return status == 200
                
    except aiohttp.ClientError as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


async def test_orac_core_connectivity(base_url: str):
    """Test ORAC Core connectivity and configuration."""
    
    print("\n📍 Testing ORAC Core Configuration")
    
    # Get current ORAC Core configuration
    url = f"{base_url}/admin/config/orac-core"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    config = await response.json()
                    core_url = config.get('orac_core_url', 'Not configured')
                    print(f"✅ Current ORAC Core URL: {core_url}")
                else:
                    print(f"❌ Failed to get ORAC Core config: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Error getting ORAC Core config: {e}")
        return False
    
    # Test connection to ORAC Core
    print("\n📍 Testing connection to ORAC Core")
    test_url = f"{base_url}/admin/config/orac-core/test"
    try:
        async with aiohttp.ClientSession() as session:
            # Test endpoint doesn't take payload, just tests current config
            async with session.post(test_url) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('success'):
                        print(f"✅ ORAC Core connection test: {result.get('message')}")
                        return True
                    else:
                        print(f"⚠️ ORAC Core connection test: {result.get('message')}")
                        print("   Note: Heartbeats will still be processed by ORAC STT")
                        return True  # Not critical if Core is down
                else:
                    print(f"❌ Connection test failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Error testing ORAC Core connection: {e}")
        return False


async def test_heartbeat_flow(base_url: str):
    """Test the complete heartbeat flow."""
    
    print("\n" + "="*60)
    print("🧪 Testing ORAC STT Heartbeat & Core Connectivity")
    print("="*60)
    
    # Test 0: Check ORAC Core connectivity
    print("\n📍 Test 0: ORAC Core Connectivity")
    await test_orac_core_connectivity(base_url)
    
    # Test 1: Send heartbeat
    print("\n📍 Test 1: Send heartbeat")
    success = await send_heartbeat(base_url)
    if not success:
        print("❌ Failed to send heartbeat")
        return False
    
    # Test 2: Check status
    print("\n📍 Test 2: Check heartbeat status")
    success = await check_heartbeat_status(base_url)
    if not success:
        print("❌ Failed to check status")
        return False
    
    # Test 3: Send multiple heartbeats from different instances
    print("\n📍 Test 3: Send heartbeats from multiple instances")
    for i in range(2):
        instance_id = f"hey_orac_test_{i+2:03d}"
        print(f"\n   Sending from instance {instance_id}")
        await send_heartbeat(base_url, instance_id)
    
    # Test 4: Check aggregated status
    print("\n📍 Test 4: Check aggregated status")
    await check_heartbeat_status(base_url)
    
    print("\n" + "="*60)
    print("✅ All heartbeat tests completed!")
    print("="*60)
    
    return True


async def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test ORAC STT heartbeat functionality")
    parser.add_argument(
        "--url",
        default="http://orin3:7272",
        help="Base URL for ORAC STT (default: http://orin3:7272)"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use localhost URL (http://localhost:7272)"
    )
    
    args = parser.parse_args()
    
    # Determine base URL
    if args.local:
        base_url = "http://localhost:7272"
    else:
        base_url = args.url
    
    print(f"🎯 Testing against: {base_url}")
    
    # Run tests
    success = await test_heartbeat_flow(base_url)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())