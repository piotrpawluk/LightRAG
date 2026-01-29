#!/usr/bin/env python3
"""Test the OpenAI client with your internal embedding endpoint"""

import asyncio
from openai import AsyncOpenAI

async def test_embedding():
    client = AsyncOpenAI(
        api_key="pU68nMPXhWgXjnIQ",
        base_url="https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl"
    )

    print("Testing embedding endpoint...")
    print(f"Base URL: {client.base_url}")

    try:
        response = await client.embeddings.create(
            model="Qwen3-Embedding-8B",
            input="This is a test sentence for embedding."
        )

        print(f"\n✅ Success!")
        print(f"Response type: {type(response)}")
        print(f"Response: {response}")

        # Try to access data attribute
        if hasattr(response, 'data'):
            print(f"\n✅ Has .data attribute")
            print(f"Data type: {type(response.data)}")
            print(f"First embedding length: {len(response.data[0].embedding)}")
        else:
            print(f"\n❌ No .data attribute")
            print(f"Response attributes: {dir(response)}")

            # If it's a list, try to access directly
            if isinstance(response, list):
                print(f"Response is a list with {len(response)} items")
                print(f"First item: {response[0]}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_embedding())
