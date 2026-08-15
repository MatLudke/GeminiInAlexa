import os
import requests
import logging
import json
import re
import time
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
import ask_sdk_core.utils as ask_utils

# Load .env file for local development/testing if present
def load_dotenv():
    env_paths = [
        os.path.join(os.path.dirname(__file__), '.env'),
        os.path.join(os.path.dirname(__file__), '..', '.env')
    ]
    for p in env_paths:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip()

load_dotenv()

# Configuration
bedrock_api_key = os.environ.get("BEDROCK_API_KEY", os.environ.get("AWS_BEARER_TOKEN_BEDROCK", ""))
tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
bedrock_region = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))
bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-5")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Sonnet 5 mode activated with web browsing. What would you like to ask?"

        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class BedrockQueryIntentHandler(AbstractRequestHandler):
    """Handler for AI Query Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("GeminiQueryIntent")(handler_input) or 
                ask_utils.is_intent_name("GptQueryIntent")(handler_input) or
                ask_utils.is_intent_name("BedrockQueryIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        query = handler_input.request_envelope.request.intent.slots["query"].value

        session_attr = handler_input.attributes_manager.session_attributes
        if "chat_history" not in session_attr:
            session_attr["chat_history"] = []
            session_attr["last_context"] = None
        
        processed_query, is_followup = process_followup_question(query, session_attr.get("last_context"))
        
        response_data = generate_bedrock_response(session_attr["chat_history"], processed_query, is_followup)
        
        if isinstance(response_data, tuple) and len(response_data) == 2:
            response_text, followup_questions = response_data
        else:
            response_text = str(response_data)
            followup_questions = []
        
        session_attr["followup_questions"] = followup_questions
        session_attr["chat_history"].append((query, response_text))
        session_attr["last_context"] = extract_context(query, response_text)
        
        response = response_text
        if followup_questions and len(followup_questions) > 0:
            response += " <break time=\"0.5s\"/> "
            response += "You could ask: "
            if len(followup_questions) > 1:
                response += ", ".join([f"'{q}'" for q in followup_questions[:-1]])
                response += f", or '{followup_questions[-1]}'"
            else:
                response += f"'{followup_questions[0]}'"
            response += ". <break time=\"0.5s\"/> What would you like to know?"
        
        reprompt_text = "You can ask me another question or say stop to end the conversation."
        if 'followup_questions' in session_attr and session_attr['followup_questions']:
            reprompt_text = "You can ask me another question, say 'next' to hear more suggestions, or say stop to end the conversation."
        
        return (
            handler_input.response_builder
                .speak(response)
                .ask(reprompt_text)
                .response
        )

# Backward compatibility aliases
GeminiQueryIntentHandler = BedrockQueryIntentHandler
GptQueryIntentHandler = BedrockQueryIntentHandler

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
        speak_output = "Leaving chat mode"
        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

def process_followup_question(question, last_context):
    """Processes a question to determine if it's a follow-up and enhances it with context if needed"""
    followup_patterns = [
        r'^(what|how|why|when|where|who|which)\s+(about|is|are|was|were|do|does|did|can|could|would|should|will)\s',
        r'^(and|but|so|then|also)\s',
        r'^(can|could|would|should|will)\s+(you|it|they|we)\s',
        r'^(is|are|was|were|do|does|did)\s+(it|that|this|they|those|these)\s',
        r'^(tell me more|elaborate|explain further)\s*',
        r'^(why|how)\?*$'
    ]
    
    is_followup = False
    for pattern in followup_patterns:
        if re.search(pattern, question.lower()):
            is_followup = True
            break
    
    return question, is_followup

def extract_context(question, response):
    return {"question": question, "response": response}

def generate_followup_questions(conversation_context, query, response_text, count=2):
    return ["Tell me more", "Explain in detail"]

def perform_tavily_search(query, max_results=5):
    """Searches the web and extracts full content from up to 5 websites using Tavily."""
    current_key = os.environ.get("TAVILY_API_KEY", tavily_api_key)
    if not current_key:
        logger.warning("No Tavily API key provided.")
        return "Search tool error: Tavily API key is not configured."
    
    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": current_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_raw_content": False
        }
        res = requests.post(url, json=payload, timeout=8)
        if not res.ok:
            return f"Search error: HTTP {res.status_code} - {res.text}"
        
        data = res.json()
        results = data.get("results", [])
        if not results:
            return "No relevant web results found."
        
        formatted_parts = []
        for idx, item in enumerate(results, 1):
            title = item.get("title", f"Website {idx}")
            link = item.get("url", "")
            content = item.get("content", "")
            formatted_parts.append(f"--- [Website {idx}: {title}] ({link}) ---\n{content}\n")
            
        return "\n".join(formatted_parts)
    except Exception as e:
        logger.error(f"Error calling Tavily: {str(e)}")
        return f"Error executing web search: {str(e)}"

def clean_speech_text(text):
    """Sanitizes text for clean Alexa SSML voice output."""
    # Remove markdown bold/italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    # Remove citation footnotes e.g. [1], [2], [Source]
    text = re.sub(r'\[\^?\d+\]', '', text)
    text = re.sub(r'\[Website \d+:[^\]]+\]', '', text)
    # Remove markdown headers and URLs
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'https?://\S+', '', text)
    # Remove angle brackets to avoid SSML breakage
    text = text.replace('&', ' and ').replace('<', '').replace('>', '')
    return text.strip()

def generate_bedrock_response(chat_history, new_question, is_followup=False):
    """
    Generates response using Amazon Bedrock Sonnet 5 with Medium Reasoning
    and 5-website deep web search tool.
    """
    current_bedrock_key = os.environ.get("BEDROCK_API_KEY", os.environ.get("AWS_BEARER_TOKEN_BEDROCK", bedrock_api_key))
    current_region = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", bedrock_region))
    current_model = os.environ.get("BEDROCK_MODEL_ID", bedrock_model_id)
    
    url = f"https://bedrock-runtime.{current_region}.amazonaws.com/model/{current_model}/converse"
    headers = {
        "Authorization": f"Bearer {current_bedrock_key}",
        "Content-Type": "application/json"
    }
    
    system_text = (
        "You are a helpful and knowledgeable assistant for Amazon Alexa powered by Sonnet 5. "
        "Provide clear, comprehensive, and up-to-date answers. "
        "When asked about current events, recent news, live scores, specific web pages, or facts, "
        "use the 'web_search' tool to inspect 5 websites and synthesize the most accurate answer. "
        "Keep your final response natural, conversational, and direct for speech synthesis on Alexa."
    )
    if is_followup:
        system_text += " Maintain context from the conversation without repeating prior statements."
    
    # Build messages array for Bedrock Converse API
    messages = []
    history_limit = 10 if not is_followup else 6
    for q, a in chat_history[-history_limit:]:
        messages.append({"role": "user", "content": [{"text": q}]})
        messages.append({"role": "assistant", "content": [{"text": a}]})
    
    messages.append({"role": "user", "content": [{"text": new_question}]})
    
    # Tool config for web search (5 websites)
    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": "web_search",
                    "description": "Searches the web and opens/extracts full contents of 5 relevant websites for real-time information, news, current events, and live web pages.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query keywords to browse 5 websites"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            }
        ]
    }
    
    # Payload with Medium Reasoning (thinking tokens budget 2048)
    request_body = {
        "system": [{"text": system_text}],
        "messages": messages,
        "toolConfig": tool_config,
        "inferenceConfig": {
            "maxTokens": 2048,
            "temperature": 1.0
        },
        "additionalModelRequestFields": {
            "thinking": {
                "type": "enabled",
                "budget_tokens": 2048
            }
        }
    }
    
    try:
        # Step 1: Initial invocation to Bedrock
        res = requests.post(url, headers=headers, json=request_body, timeout=25)
        
        # If thinking is not supported for a fallback model or format error, retry without thinking
        if not res.ok and "thinking" in res.text:
            logger.warning("Retrying without thinking configuration...")
            del request_body["additionalModelRequestFields"]
            request_body["inferenceConfig"]["temperature"] = 0.7
            res = requests.post(url, headers=headers, json=request_body, timeout=25)
        
        if not res.ok:
            error_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("message", res.text)
            return f"Amazon Bedrock error {res.status_code}: {error_msg}", []
        
        res_json = res.json()
        output_message = res_json.get("output", {}).get("message", {})
        stop_reason = res_json.get("stopReason", "")
        
        # Step 2: Handle Tool Use (Web Browsing 5 websites)
        if stop_reason == "tool_use":
            content_blocks = output_message.get("content", [])
            messages.append(output_message)
            
            tool_results = []
            for block in content_blocks:
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_use_id = tool_use.get("toolUseId")
                    tool_name = tool_use.get("name")
                    tool_input = tool_use.get("input", {})
                    
                    if tool_name == "web_search":
                        search_query = tool_input.get("query", new_question)
                        search_output = perform_tavily_search(search_query, max_results=5)
                        tool_results.append({
                            "toolResult": {
                                "toolUseId": tool_use_id,
                                "content": [{"text": search_output}]
                            }
                        })
            
            # Send tool results back to Bedrock for final synthesis
            messages.append({"role": "user", "content": tool_results})
            request_body["messages"] = messages
            
            followup_res = requests.post(url, headers=headers, json=request_body, timeout=25)
            if followup_res.ok:
                res_json = followup_res.json()
                output_message = res_json.get("output", {}).get("message", {})
            else:
                logger.error(f"Follow-up tool response failed: {followup_res.text}")
        
        # Step 3: Extract text parts (excluding thinking blocks)
        content_parts = output_message.get("content", [])
        text_responses = []
        for part in content_parts:
            if "text" in part:
                text_responses.append(part["text"])
        
        raw_text = " ".join(text_responses).strip() if text_responses else "I couldn't generate a response."
        cleaned_text = clean_speech_text(raw_text)
        
        followup_questions = generate_followup_questions(
            chat_history + [(new_question, cleaned_text)], 
            new_question, 
            cleaned_text
        )
        return cleaned_text, followup_questions
        
    except Exception as e:
        logger.error(f"Error generating Bedrock response: {str(e)}")
        return f"Error connecting to Amazon Bedrock: {str(e)}", []

# Alias for compatibility
generate_gemini_response = generate_bedrock_response
generate_gpt_response = generate_bedrock_response

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
sb.add_request_handler(BedrockQueryIntentHandler())
sb.add_request_handler(ClearContextIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
