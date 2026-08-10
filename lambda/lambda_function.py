import os
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
import ask_sdk_core.utils as ask_utils
import requests
import logging
import json
import re

# Set your Google AI Studio API key
api_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "YOUR_API_KEY"))

model = "gemini-3.6-flash"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Gemini mode activated"

        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class GeminiQueryIntentHandler(AbstractRequestHandler):
    """Handler for Gemini Query Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GeminiQueryIntent")(handler_input) or ask_utils.is_intent_name("GptQueryIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        query = handler_input.request_envelope.request.intent.slots["query"].value

        session_attr = handler_input.attributes_manager.session_attributes
        if "chat_history" not in session_attr:
            session_attr["chat_history"] = []
            session_attr["last_context"] = None
        
        # Process the query to determine if it's a follow-up question
        processed_query, is_followup = process_followup_question(query, session_attr.get("last_context"))
        
        # Generate response with enhanced context handling
        response_data = generate_gemini_response(session_attr["chat_history"], processed_query, is_followup)
        
        # Handle the response data which could be a tuple or string
        if isinstance(response_data, tuple) and len(response_data) == 2:
            response_text, followup_questions = response_data
        else:
            # Fallback for error cases
            response_text = str(response_data)
            followup_questions = []
        
        # Store follow-up questions in the session
        session_attr["followup_questions"] = followup_questions
        
        # Update the conversation history with just the response text, not the questions
        session_attr["chat_history"].append((query, response_text))
        session_attr["last_context"] = extract_context(query, response_text)
        
        # Format the response with follow-up suggestions if available
        response = response_text
        if followup_questions and len(followup_questions) > 0:
            # Add a short pause before the suggestions
            response += " <break time=\"0.5s\"/> "
            response += "You could ask: "
            # Join with 'or' for the last question
            if len(followup_questions) > 1:
                response += ", ".join([f"'{q}'" for q in followup_questions[:-1]])
                response += f", or '{followup_questions[-1]}'"
            else:
                response += f"'{followup_questions[0]}'"
            response += ". <break time=\"0.5s\"/> What would you like to know?"
        
        # Prepare response with reprompt that includes the follow-up questions
        reprompt_text = "You can ask me another question or say stop to end the conversation."
        if 'followup_questions' in session_attr and session_attr['followup_questions']:
            reprompt_text = "You can ask me another question, say 'next' to hear more suggestions, or say stop to end the conversation."
        
        return (
            handler_input.response_builder
                .speak(response)
                .ask(reprompt_text)
                .response
        )

# Maintain GptQueryIntentHandler alias for backwards compatibility
GptQueryIntentHandler = GeminiQueryIntentHandler

class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors."""
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Leaving Gemini mode"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

def process_followup_question(question, last_context):
    """Processes a question to determine if it's a follow-up and enhances it with context if needed"""
    # Common follow-up indicators
    followup_patterns = [
        r'^(what|how|why|when|where|who|which)\s+(about|is|are|was|were|do|does|did|can|could|would|should|will)\s',
        r'^(and|but|so|then|also)\s',
        r'^(can|could|would|should|will)\s+(you|it|they|we)\s',
        r'^(is|are|was|were|do|does|did)\s+(it|that|this|they|those|these)\s',
        r'^(tell me more|elaborate|explain further)\s*',
        r'^(why|how)\?*$'
    ]
    
    is_followup = False
    
    # Check if the question matches any follow-up patterns
    for pattern in followup_patterns:
        if re.search(pattern, question.lower()):
            is_followup = True
            break
    
    # If it's a follow-up and we have context, context is handled in generate_gemini_response
    return question, is_followup

def extract_context(question, response):
    """Extracts the main context from a Q&A pair for future reference"""
    return {"question": question, "response": response}

def generate_followup_questions(conversation_context, query, response_text, count=2):
    """Returns concise follow-up question suggestions without extra API calls to save quota."""
    return ["Tell me more", "Explain in detail"]

def generate_gemini_response(chat_history, new_question, is_followup=False):
    """Generates a Gemini response to a question with enhanced context handling using Google AI Studio API"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    system_message = "You are a helpful assistant. Provide clear, comprehensive, and up-to-date answers. Feel free to explain in detail."
    if is_followup:
        system_message += " This is a follow-up question to the previous conversation. Maintain context without repeating information already provided."
    
    contents = []
    
    # Include relevant conversation history
    history_limit = 10 if not is_followup else 5
    for question, answer in chat_history[-history_limit:]:
        contents.append({"role": "user", "parts": [{"text": question}]})
        contents.append({"role": "model", "parts": [{"text": answer}]})
    
    # Add the new question
    contents.append({"role": "user", "parts": [{"text": new_question}]})
    
    data = {
        "systemInstruction": {
            "parts": [{"text": system_message}]
        },
        "contents": contents,
        "tools": [
            {"googleSearch": {}}
        ],
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0.7,
            "thinkingConfig": {
                "thinkingLevel": "MEDIUM"
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response_data = response.json()
        if response.ok:
            candidates = response_data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    response_text = parts[0].get('text', '')
                else:
                    finish_reason = candidates[0].get('finishReason', 'UNKNOWN')
                    response_text = f"No response generated (Reason: {finish_reason})."
            else:
                response_text = "No response candidates returned."
            
            # Generate follow-up questions for the response
            try:
                followup_questions = generate_followup_questions(
                    chat_history + [(new_question, response_text)], 
                    new_question, 
                    response_text
                )
                logger.info(f"Generated follow-up questions: {followup_questions}")
            except Exception as e:
                logger.error(f"Error generating follow-up questions: {str(e)}")
                followup_questions = []
            
            return response_text, followup_questions
        else:
            error_msg = response_data.get('error', {}).get('message', response.text)
            return f"Error {response.status_code}: {error_msg}", []
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return f"Error generating response: {str(e)}", []

# Alias for backwards compatibility
generate_gpt_response = generate_gemini_response

class ClearContextIntentHandler(AbstractRequestHandler):
    """Handler for clearing conversation context."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ClearContextIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []
        session_attr["last_context"] = None
        
        speak_output = "I've cleared our conversation history. What would you like to talk about?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GeminiQueryIntentHandler())
sb.add_request_handler(ClearContextIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()

