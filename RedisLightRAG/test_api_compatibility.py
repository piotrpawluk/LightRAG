#!/usr/bin/env python3
"""
Complete API compatibility checker for OpenAI client v1.109.1
Tests response headers, structure, and data types
"""

import asyncio
import httpx
import json

async def check_api_compatibility():
    url = "https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1/embeddings"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer pU68nMPXhWgXjnIQ"
    }

    payload = {
        "model": "Qwen3-Embedding-8B",
        "input": "Test sentence for compatibility check."
    }

    print("=" * 80)
    print("OpenAI API Compatibility Checker")
    print("=" * 80)

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, json=payload, headers=headers)

        print(f"\n1. HTTP STATUS CODE")
        print(f"   Status: {response.status_code}")
        print(f"   ✓ Expected: 200" if response.status_code == 200 else f"   ✗ Expected: 200")

        print(f"\n2. RESPONSE HEADERS")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        content_type_ok = 'application/json' in response.headers.get('content-type', '').lower()
        print(f"   ✓ Correct" if content_type_ok else f"   ✗ Must be 'application/json'")

        # Check for required headers
        print(f"\n3. CORS & ADDITIONAL HEADERS")
        for header in ['access-control-allow-origin', 'x-request-id']:
            value = response.headers.get(header, 'Not set')
            print(f"   {header}: {value}")

        print(f"\n4. RESPONSE BODY STRUCTURE")
        data = response.json()
        print(f"   Type: {type(data)}")
        print(f"   ✓ Is dict" if isinstance(data, dict) else f"   ✗ Must be dict, got {type(data)}")

        # Check required top-level fields
        print(f"\n5. REQUIRED TOP-LEVEL FIELDS")
        required_fields = {
            'object': (str, 'list'),
            'data': (list, None),
            'model': (str, None),
            'usage': (dict, None)
        }

        for field, (expected_type, expected_value) in required_fields.items():
            if field in data:
                value = data[field]
                type_ok = isinstance(value, expected_type)
                print(f"   ✓ '{field}': {type(value).__name__}", end="")
                if expected_value:
                    value_ok = value == expected_value
                    print(f" = '{value}'" if value_ok else f" = '{value}' (expected '{expected_value}')")
                else:
                    print()

                if not type_ok:
                    print(f"      ✗ Wrong type! Expected {expected_type.__name__}")
            else:
                print(f"   ✗ Missing required field: '{field}'")

        # Check data array structure
        if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
            print(f"\n6. DATA ARRAY STRUCTURE")
            first_item = data['data'][0]
            print(f"   Array length: {len(data['data'])}")
            print(f"   First item type: {type(first_item)}")

            required_data_fields = {
                'object': (str, 'embedding'),
                'embedding': (list, None),
                'index': (int, None)
            }

            for field, (expected_type, expected_value) in required_data_fields.items():
                if field in first_item:
                    value = first_item[field]
                    type_ok = isinstance(value, expected_type)

                    if field == 'embedding':
                        print(f"   ✓ '{field}': {type(value).__name__} with {len(value)} dimensions")
                        # Check that all embeddings are floats
                        all_floats = all(isinstance(x, (int, float)) for x in value[:10])
                        print(f"      ✓ All float values" if all_floats else "      ✗ Non-float values detected")
                    else:
                        print(f"   ✓ '{field}': {type(value).__name__} = {value}")

                    if not type_ok:
                        print(f"      ✗ Wrong type! Expected {expected_type.__name__}")
                else:
                    print(f"   ✗ Missing required field in data[0]: '{field}'")

        # Check usage structure
        if 'usage' in data and isinstance(data['usage'], dict):
            print(f"\n7. USAGE OBJECT STRUCTURE")
            required_usage_fields = ['prompt_tokens', 'total_tokens']

            for field in required_usage_fields:
                if field in data['usage']:
                    value = data['usage'][field]
                    type_ok = isinstance(value, int)
                    print(f"   ✓ '{field}': {value}" if type_ok else f"   ✗ '{field}': {value} (must be int)")
                else:
                    print(f"   ✗ Missing required field in usage: '{field}'")

        # Check for extra/unknown fields that might cause issues
        print(f"\n8. EXTRA FIELDS (may cause strict parsing issues)")
        known_fields = {'object', 'data', 'model', 'usage'}
        extra_fields = set(data.keys()) - known_fields
        if extra_fields:
            print(f"   ⚠ Extra fields found: {extra_fields}")
            print(f"   These may cause issues with strict Pydantic validation")
        else:
            print(f"   ✓ No extra fields")

        # Field order check
        print(f"\n9. FIELD ORDER")
        actual_order = list(data.keys())
        recommended_order = ['object', 'data', 'model', 'usage']
        print(f"   Actual:      {actual_order}")
        print(f"   Recommended: {recommended_order}")
        if actual_order == recommended_order:
            print(f"   ✓ Matches OpenAI order")
        else:
            print(f"   ⚠ Different order (usually OK, but some parsers may be sensitive)")

        print(f"\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        # Generate recommendations
        recommendations = []

        if response.status_code != 200:
            recommendations.append("- Fix HTTP status code to return 200 for successful responses")

        if not content_type_ok:
            recommendations.append("- Set Content-Type header to 'application/json'")

        if not isinstance(data, dict):
            recommendations.append("- Response body must be a JSON object (dict), not array")

        if 'object' not in data or data.get('object') != 'list':
            recommendations.append("- Add 'object': 'list' field at top level")

        if extra_fields:
            recommendations.append(f"- Remove extra fields: {extra_fields}")

        if actual_order != recommended_order:
            recommendations.append("- Reorder response fields to match OpenAI: object, data, model, usage")

        if recommendations:
            print("\n⚠ COMPATIBILITY ISSUES FOUND:")
            for rec in recommendations:
                print(rec)
        else:
            print("\n✓ API appears to be fully compatible with OpenAI format!")
            print("  The issue may be in the OpenAI client version or Pydantic parsing.")

        print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(check_api_compatibility())
