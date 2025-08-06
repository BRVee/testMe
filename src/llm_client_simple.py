"""
Simple Google AI (Gemini) client using API key - no GCP setup needed!
"""
import os
import json
import requests
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from .prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES

# Load environment variables
load_dotenv()


class SimpleGeminiClient:
    """Simple Gemini client using API key (via Google AI Studio)"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client with API key
        
        Args:
            api_key: Google AI API key (uses env var if not provided)
        """
        self.api_key = api_key or os.getenv("GOOGLE_AI_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided or set in GOOGLE_AI_API_KEY env var")
        
        # Use Gemini 1.5 Flash for fast responses
        self.model = "gemini-1.5-flash"
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
    
    def analyze_screen(self, screen_dump: Dict[str, Any], user_goal: str) -> Dict[str, Any]:
        """
        Analyze screen and determine next action
        
        Args:
            screen_dump: The UI dump from parse_for_llm()
            user_goal: What the user wants to achieve
            
        Returns:
            Dict with action, element_index, reason, confidence
        """
        # Build the prompt
        full_prompt = f"""{SYSTEM_PROMPT}

{FEW_SHOT_EXAMPLES}

Current user goal: {user_goal}

Current screen UI elements:
{json.dumps(screen_dump['screen_elements'], indent=2)}

Screen summary:
- Total elements: {screen_dump['total_elements']}
- Clickable elements: {screen_dump['clickable_elements']}
- Element types: {json.dumps(screen_dump['element_types'])}

Based on the user's goal and current screen, what action should be taken?
Respond with valid JSON only."""

        # Prepare request
        headers = {
            "Content-Type": "application/json",
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": full_prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 1,
                "topP": 0.95,
                "maxOutputTokens": 256,
                "responseMimeType": "application/json"
            }
        }
        
        # Make request
        response = requests.post(
            f"{self.api_url}?key={self.api_key}",
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
        # Parse response
        result = response.json()
        
        try:
            # Extract the generated text
            generated_text = result['candidates'][0]['content']['parts'][0]['text']
            
            # Parse JSON response
            action_result = json.loads(generated_text)
            
            # Validate response structure
            required_fields = ["action", "element_index", "reason", "confidence"]
            if not all(field in action_result for field in required_fields):
                raise ValueError("Invalid response format from LLM")
            
            return action_result
            
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Failed to parse response: {result}")
            raise ValueError(f"Failed to parse LLM response: {e}")


# Singleton instance
_simple_llm_instance = None

def get_simple_llm_client() -> SimpleGeminiClient:
    """Get or create simple LLM client instance"""
    global _simple_llm_instance
    if _simple_llm_instance is None:
        _simple_llm_instance = SimpleGeminiClient()
    return _simple_llm_instance