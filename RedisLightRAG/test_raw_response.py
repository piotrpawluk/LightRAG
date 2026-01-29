#!/usr/bin/env python3
"""Capture raw HTTP response to see the actual format"""

import asyncio
import httpx
import json

async def test_raw_embedding():
    url = "https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1/embeddings"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer pU68nMPXhWgXjnIQ"
    }

    payload = {
        "model": "Qwen3-Embedding-8B",
        "input": "This is a test sentence for embedding."
    }

    print(f"Calling: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, json=payload, headers=headers)

        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}\n")

        raw_json = response.json()
        print(f"Raw JSON response:")
        print(json.dumps(raw_json, indent=2))

        print(f"\nResponse type: {type(raw_json)}")
        print(f"Has 'data' key: {'data' in raw_json if isinstance(raw_json, dict) else 'N/A (not a dict)'}")

        if isinstance(raw_json, dict) and 'data' in raw_json:
            print(f"Data length: {len(raw_json['data'])}")
            print(f"First embedding length: {len(raw_json['data'][0]['embedding'])}")

if __name__ == "__main__":
    asyncio.run(test_raw_embedding())
