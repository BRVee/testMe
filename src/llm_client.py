"""
Vertex AI client for UI automation with smart prompt management
"""
import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from dotenv import load_dotenv
from .prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES

# Load environment variables
load_dotenv()


class UIAutomationLLM:
    """Smart LLM client for UI automation that maintains context"""
    
    def __init__(self, project_id: Optional[str] = None, location: str = "us-central1"):
        """
        Initialize Vertex AI client
        
        Args:
            project_id: GCP project ID (uses env var if not provided)
            location: GCP region for Vertex AI
        """
        self.project_id = project_id or os.getenv("VERTEX_AI_PROJECT_ID")
        self.location = location
        self.model_name = "gemini-1.5-flash-001"  # Fast model for low latency
        
        if not self.project_id:
            raise ValueError("Project ID must be provided or set in VERTEX_AI_PROJECT_ID env var")
        
        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)
        
        # Configure model with system instruction
        self.model = GenerativeModel(
            self.model_name,
            system_instruction=SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES
        )
        
        # Generation config for consistent JSON output
        self.generation_config = GenerationConfig(
            temperature=0.1,  # Low temperature for consistent outputs
            top_p=0.95,
            max_output_tokens=256,  # Keep responses concise
            response_mime_type="application/json"  # Force JSON output
        )
    
    def analyze_screen(self, screen_dump: Dict[str, Any], user_goal: str) -> Dict[str, Any]:
        """
        Analyze screen and determine next action
        
        Args:
            screen_dump: The UI dump from parse_for_llm()
            user_goal: What the user wants to achieve
            
        Returns:
            Dict with action, element_index, reason, confidence
        """
        # Prepare context-aware prompt
        prompt = f"""
Current user goal: {user_goal}

Current screen UI elements:
{json.dumps(screen_dump['screen_elements'], indent=2)}

Screen summary:
- Total elements: {screen_dump['total_elements']}
- Clickable elements: {screen_dump['clickable_elements']}
- Element types: {json.dumps(screen_dump['element_types'])}

Based on the user's goal and current screen, what action should be taken?
"""
        
        try:
            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            # Parse JSON response
            result = json.loads(response.text)
            
            # Validate response structure
            required_fields = ["action", "element_index", "reason", "confidence"]
            if not all(field in result for field in required_fields):
                raise ValueError("Invalid response format from LLM")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response: {response.text}")
            raise ValueError(f"LLM returned invalid JSON: {e}")
        except Exception as e:
            print(f"Error calling LLM: {e}")
            raise
    
    def analyze_with_history(self, screen_dump: Dict[str, Any], user_goal: str, 
                           history: list = None) -> Dict[str, Any]:
        """
        Analyze screen with conversation history for multi-step tasks
        
        Args:
            screen_dump: Current UI state
            user_goal: Current objective
            history: List of previous actions taken
            
        Returns:
            Next action to take
        """
        history_text = ""
        if history:
            history_text = "\nPrevious actions taken:\n"
            for i, action in enumerate(history, 1):
                history_text += f"{i}. {action.get('action')} on {action.get('element_label')} - {action.get('result', 'success')}\n"
        
        # Build enhanced prompt with history
        prompt = f"""
Current user goal: {user_goal}
{history_text}
Current screen UI elements:
{json.dumps(screen_dump['screen_elements'], indent=2)}

Screen summary:
- Total elements: {screen_dump['total_elements']}
- Clickable elements: {screen_dump['clickable_elements']}

What should be the next action to achieve the goal?
"""
        
        response = self.model.generate_content(
            prompt,
            generation_config=self.generation_config
        )
        
        return json.loads(response.text)


# Singleton instance for reuse
_llm_instance = None

def get_llm_client() -> UIAutomationLLM:
    """Get or create LLM client instance"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = UIAutomationLLM()
    return _llm_instance