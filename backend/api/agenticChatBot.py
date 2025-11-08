import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
from send_email import sendEmail

load_dotenv()

# Initialize Gemini client
api_key = os.getenv("VITE_GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

# Store conversation state
conversation_state = {
    "pending_email": None,
    "pending_recipient": None,
    "waiting_for_confirmation": False,
    "waiting_for_topic": False,
    "waiting_for_recipient": False
}

def reset_state():
    """Reset conversation state"""
    conversation_state["pending_email"] = None
    conversation_state["pending_recipient"] = None
    conversation_state["waiting_for_confirmation"] = False
    conversation_state["waiting_for_topic"] = False
    conversation_state["waiting_for_recipient"] = False

def generate_email(topic, business_context=""):
    """Generate a professional email using Gemini"""
    prompt = f"""Write a professional email about: {topic}

Business context: {business_context if business_context else 'General business communication'}

Requirements:
- Professional and concise
- Clear subject line
- Proper greeting and closing
- 3-5 sentences in body

Format the email with:
Subject: [subject line]

[email body]

Best regards,
[Sender name]"""

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt
    )
    
    return response.text

def analyze_business_idea(business_idea):
    """Generate pros and cons analysis of business idea"""
    prompt = f"""Analyze this business idea and provide a balanced assessment:

Business Idea: {business_idea}

Please provide:
1. PROS (3-5 strong points)
2. CONS (3-5 potential challenges or weaknesses)

Be specific, constructive, and professional. Format as a clear pros and cons list."""

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt
    )
    
    return response.text

def classify_intent(user_message):
    """Classify user's intent using Gemini"""
    prompt = f"""Classify the user's intent from this message: "{user_message}"

Possible intents:
1. "email" - User wants to send an email (keywords: send email, email, write email, contact, reach out)
2. "feedback" - User wants feedback on their business idea (keywords: how is my idea, feedback, what do you think, pros cons, analyze my idea)
3. "other" - Any other request

Respond with ONLY ONE WORD: email, feedback, or other"""

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt
    )
    
    return response.text.strip().lower()

def extract_email_info(user_message):
    """Extract recipient and topic from email request"""
    import re
    
    # Check for email addresses in the message
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, user_message)
    
    prompt = f"""Extract information from this email request: "{user_message}"

Extract:
1. Recipient: Who should receive the email? 
   - If they mention "connection", "network", "networking", "my connection", return "network"
   - If they mention "Alexey" or specific person, return that name
   - If you see an email address, return "email_provided"
   - Otherwise return "unknown"

2. Topic: What is the email about?
   - Extract the main subject/topic
   - If no topic mentioned, return "unknown"

3. Email Address: If an email address is mentioned, extract it. Otherwise return "none"

Respond in JSON format:
{{"recipient": "...", "topic": "...", "email": "..."}}"""

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt
    )
    
    try:
        result = json.loads(response.text)
        # Override with regex match if found
        if email_match:
            result["email"] = email_match.group(0)
            result["recipient"] = "email_provided"
        return result
    except:
        # Fallback to regex if JSON parsing fails
        if email_match:
            return {"recipient": "email_provided", "topic": "unknown", "email": email_match.group(0)}
        return {"recipient": "unknown", "topic": "unknown", "email": "none"}

def handle_chat(user_message, business_idea="", chat_history=None):
    """
    Main chatbot handler
    
    Args:
        user_message: The user's message
        business_idea: The startup idea from the dashboard
        chat_history: List of previous messages (optional, for context)
    
    Returns:
        dict with 'response' and 'action' fields
    """
    
    # Handle pending confirmation
    if conversation_state["waiting_for_confirmation"]:
        if any(word in user_message.lower() for word in ["yes", "yeah", "sure", "send", "ok", "yep"]):
            try:
                # Send the email
                sendEmail(
                    conversation_state["pending_recipient"],
                    conversation_state["pending_email"]
                )
                reset_state()
                return {
                    "response": "✓ Email sent successfully! Let me know if I can help you with anything else.",
                    "action": "email_sent"
                }
            except Exception as e:
                reset_state()
                return {
                    "response": f"Sorry, there was an error sending the email: {str(e)}. Let me know if you need help with anything else.",
                    "action": "error"
                }
        else:
            reset_state()
            return {
                "response": "No problem! Let me know if I can help you with anything else.",
                "action": "cancelled"
            }
    
    # Handle waiting for recipient (when user was asked "Who would you like to send the email to?")
    if conversation_state.get("waiting_for_recipient", False):
        import re
        
        # Check if user provided an email address
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, user_message)
        
        if email_match:
            actual_recipient = email_match.group(0)
            recipient_name = actual_recipient
        elif any(word in user_message.lower() for word in ["connection", "network", "alexey"]):
            actual_recipient = "alexeyplagov@gmail.com"
            recipient_name = "Alexey Plagov"
        else:
            # Try to extract with AI
            email_info = extract_email_info(user_message)
            provided_email = email_info.get("email", "none")
            
            if provided_email != "none":
                actual_recipient = provided_email
                recipient_name = provided_email
            else:
                return {
                    "response": "I couldn't find an email address. Please provide either:\n• An email address (e.g., person@example.com)\n• Say 'my connection' for Alexey Plagov",
                    "action": "need_recipient"
                }
        
        # Now ask for topic
        conversation_state["pending_recipient"] = actual_recipient
        conversation_state["waiting_for_recipient"] = False
        conversation_state["waiting_for_topic"] = True
        
        return {
            "response": f"Great! I'll draft an email to {recipient_name}. What should the email be about?",
            "action": "need_topic"
        }
    
    # Handle waiting for email topic
    if conversation_state["waiting_for_topic"]:
        topic = user_message
        recipient = conversation_state["pending_recipient"]
        
        # Generate email
        email_content = generate_email(topic, business_idea)
        
        conversation_state["pending_email"] = email_content
        conversation_state["waiting_for_topic"] = False
        conversation_state["waiting_for_confirmation"] = True
        
        return {
            "response": f"Here's the email I drafted:\n\n{email_content}\n\nDo you want to send this?",
            "action": "email_generated"
        }
    
    # Classify intent
    intent = classify_intent(user_message)
    
    if intent == "email":
        # Extract email information
        email_info = extract_email_info(user_message)
        recipient = email_info.get("recipient", "unknown")
        topic = email_info.get("topic", "unknown")
        provided_email = email_info.get("email", "none")
        
        # Determine actual recipient email
        actual_recipient = None
        recipient_name = None
        
        # Case 1: User mentioned "connection" or "network" - use Alexey
        if recipient == "network" or "alexey" in recipient.lower():
            actual_recipient = "alexeyplagov@gmail.com"
            recipient_name = "Alexey Plagov"
        
        # Case 2: User provided an email address
        elif recipient == "email_provided" and provided_email != "none":
            actual_recipient = provided_email
            recipient_name = provided_email
        
        # Case 3: No recipient info
        elif recipient == "unknown":
            conversation_state["waiting_for_recipient"] = True
            return {
                "response": "Who would you like me to send the email to? You can provide an email address or say 'to my connection'.",
                "action": "need_recipient"
            }
        
        # Case 4: Named person we don't have email for
        else:
            return {
                "response": f"I don't have {recipient}'s email address. You can either:\n• Provide their email address directly\n• Send to your network connection (Alexey Plagov)\n\nWhat would you like to do?",
                "action": "invalid_recipient"
            }
        
        # Check if we have topic
        if topic == "unknown":
            conversation_state["pending_recipient"] = actual_recipient
            conversation_state["waiting_for_topic"] = True
            return {
                "response": f"Sure! I'll draft an email to {recipient_name}. What should the email be about?",
                "action": "need_topic"
            }
        
        # Generate email - we have both recipient and topic
        email_content = generate_email(topic, business_idea)
        
        conversation_state["pending_email"] = email_content
        conversation_state["pending_recipient"] = actual_recipient
        conversation_state["waiting_for_confirmation"] = True
        
        return {
            "response": f"Here's the email I drafted for {recipient_name}:\n\n{email_content}\n\nDo you want to send this?",
            "action": "email_generated"
        }
    
    elif intent == "feedback":
        if not business_idea:
            return {
                "response": "I don't see a business idea to analyze. Please enter your startup idea in the text box at the top of the dashboard first!",
                "action": "no_business_idea"
            }
        
        analysis = analyze_business_idea(business_idea)
        
        return {
            "response": analysis,
            "action": "feedback_provided"
        }
    
    else:
        return {
            "response": "This feature is not built out yet. I can help you with:\n• Sending emails to your network\n• Analyzing your business idea\n\nWhat would you like to do?",
            "action": "feature_unavailable"
        }
