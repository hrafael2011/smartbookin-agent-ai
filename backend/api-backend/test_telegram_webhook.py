import httpx
import asyncio
import json

async def test_webhook():
    url = "http://localhost:8000/webhooks/telegram"
    
    # 1. Simulate First Greeting (New user)
    payload_1 = {
        "message": {
            "message_id": 12345,
            "from": {"id": 11223344, "first_name": "Test"},
            "chat": {"id": 11223344, "type": "private"},
            "date": 1614552000,
            "text": "Hola"
        }
    }
    
    # 2. Simulate Name Response
    payload_2 = {
        "message": {
            "message_id": 12346,
            "from": {"id": 11223344, "first_name": "Test"},
            "chat": {"id": 11223344, "type": "private"},
            "date": 1614552001,
            "text": "Hendrick Rafael"
        }
    }
    
    # 3. Simulate Booking intent
    payload_3 = {
        "message": {
            "message_id": 12347,
            "from": {"id": 11223344, "first_name": "Test"},
            "chat": {"id": 11223344, "type": "private"},
            "date": 1614552002,
            "text": "Quiero reservar un corte de pelo para mañana"
        }
    }

    async with httpx.AsyncClient() as client:
        print("--- Testing New User Greeting ---")
        try:
            r1 = await client.post(url, json=payload_1)
            print(f"Status: {r1.status_code}")
            print(f"Response: {r1.json()}")
        except Exception as e:
            print(f"Error: {e}")

        print("\n--- Testing Name Provision ---")
        try:
            r2 = await client.post(url, json=payload_2)
            print(f"Status: {r2.status_code}")
            print(f"Response: {r2.json()}")
        except Exception as e:
            print(f"Error: {e}")

        print("\n--- Testing Booking Intent ---")
        try:
            r3 = await client.post(url, json=payload_3)
            print(f"Status: {r3.status_code}")
            print(f"Response: {r3.json()}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("Pre-requisite: The FastAPI server must be running on http://localhost:8000")
    asyncio.run(test_webhook())
