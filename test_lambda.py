#!/usr/bin/env python3
"""
Test script for the Alexa Gemini lambda function
"""
import os
import sys
import json
from unittest.mock import MagicMock

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda'))

# Set up environment variable for API key if not already set
from lambda_function import lambda_handler

def create_alexa_request(query):
    """Create a mock Alexa request for testing"""
    return {
        "version": "1.0",
        "session": {
            "new": False,
            "sessionId": "test-session-id",
            "application": {
                "applicationId": "test-app-id"
            },
            "attributes": {},
            "user": {
                "userId": "test-user-id"
            }
        },
        "context": {
            "System": {
                "application": {
                    "applicationId": "test-app-id"
                },
                "user": {
                    "userId": "test-user-id"
                },
                "device": {
                    "deviceId": "test-device-id",
                    "supportedInterfaces": {}
                }
            }
        },
        "request": {
            "type": "IntentRequest",
            "requestId": "test-request-id",
            "timestamp": "2025-12-10T10:00:00Z",
            "locale": "en-US",
            "intent": {
                "name": "GeminiQueryIntent",
                "confirmationStatus": "NONE",
                "slots": {
                    "query": {
                        "name": "query",
                        "value": query,
                        "confirmationStatus": "NONE"
                    }
                }
            }
        }
    }

def test_query(query):
    """Test the lambda function with a specific query"""
    print(f"\n{'='*60}")
    print(f"Testing query: '{query}'")
    print('='*60)
    
    # Create the Alexa request
    event = create_alexa_request(query)
    context = {}
    
    try:
        # Call the lambda handler
        response = lambda_handler(event, context)
        
        # Extract the speech response
        if 'response' in response and 'outputSpeech' in response['response']:
            speech_text = response['response']['outputSpeech'].get('ssml', '')
            # Remove SSML tags for cleaner output
            import re
            clean_text = re.sub(r'<[^>]+>', '', speech_text)
            
            print(f"\n✅ Response received:")
            print(f"{clean_text}\n")
            
            # Check if there's a reprompt
            if 'reprompt' in response['response']:
                reprompt_text = response['response']['reprompt'].get('outputSpeech', {}).get('ssml', '')
                clean_reprompt = re.sub(r'<[^>]+>', '', reprompt_text)
                print(f"Reprompt: {clean_reprompt}\n")
            
            # Show session attributes if any
            if 'sessionAttributes' in response:
                print(f"Session has chat history: {'chat_history' in response['sessionAttributes']}")
                if 'followup_questions' in response['sessionAttributes']:
                    print(f"Follow-up questions: {response['sessionAttributes']['followup_questions']}")
            
            return True
        else:
            print(f"❌ Unexpected response format: {json.dumps(response, indent=2)}")
            return False
            
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Test the specific query
    test_query("who are you?")
    
    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)

