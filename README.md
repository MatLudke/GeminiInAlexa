# Gemini in Alexa 🤖⚡

A custom Alexa Skill that integrates Google's **Gemini 3.5 Flash** model via the **Google AI Studio API** into Amazon Alexa, enabling natural conversational interactions, context memory, and follow-up query suggestions directly on your Echo devices.

## Features ✨

- **Google AI Studio Integration**: Powered by Google's fast and intelligent `gemini-3.5-flash` model.
- **Conversational Memory**: Remembers prior questions and answers within a session for natural follow-up queries.
- **Proactive Follow-up Suggestions**: Automatically suggests short follow-up prompts after answers.
- **Multilingual Support**: Interaction models configured for 15+ locales (English, Spanish, French, German, Italian, Japanese, Hindi, Portuguese, etc.).
- **Zero Native Dependencies**: Lightweight Python Lambda backend using `ask-sdk-core` and standard HTTP requests.

## Prerequisites 📋

1. An [Amazon Developer Account](https://developer.amazon.com/) (to create and host the Alexa Skill).
2. A [Google AI Studio API Key](https://aistudio.google.com/app/apikey).

## Setup & Deployment Guide 🚀

### 1. Create the Alexa Skill
1. Go to the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) and click **Create Skill**.
2. Name your skill (e.g., `Gemini` or `Chat`) and choose your primary locale.
3. Under **Experience/Model**, choose **Other** -> **Custom**.
4. Under **Hosting Services**, select **Alexa-hosted (Python)**.
5. Choose **Import Skill** and enter the repository URL:
   ```text
   https://github.com/MatLudke/GeminiInAlexa.git
   ```
6. Click **Import**.

### 2. Configure the Interaction Model
If you didn't import the repository directly:
1. In the **Build** tab, select **JSON Editor**.
2. Copy and paste the contents of [`json_editor.json`](json_editor.json).
3. Click **Save Model** and then **Build Model**.

### 3. Configure the Lambda Backend
1. Go to the **Code** tab in the Alexa Console.
2. In `lambda/lambda_function.py`, set your Google AI Studio API Key:
   ```python
   api_key = "YOUR_GOOGLE_AI_STUDIO_API_KEY"
   ```
   *Or set environment variables `GEMINI_API_KEY` or `GOOGLE_API_KEY` in AWS Lambda settings.*
3. Ensure `requirements.txt` contains:
   ```text
   ask-sdk-core==1.19.0
   boto3==1.28.78
   requests>=2.20.0
   ```
4. Click **Save** and **Deploy**.

## Testing & Usage 💬

1. Go to the **Test** tab in the Alexa Developer Console and enable **Skill testing** in "Development".
2. Test by typing or speaking:
   - *"Alexa, open chat"*
   - *"Ask chat who won the world cup in 1970"*
   - *"What about 1994?"* (Follow-up query)
   - *"Clear history"* or *"Stop"*

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
