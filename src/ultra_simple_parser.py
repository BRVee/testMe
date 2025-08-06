"""
Ultra-simple parser that just works - focused on getting actionable elements
"""
from lxml import etree
from typing import Dict, List, Any
import re


def parse_actionable_elements(xml_path: str) -> Dict[str, Any]:
    """
    Dead simple parser that extracts only what matters for UI automation.
    No fancy hierarchies, just actionable elements with clear labels.
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    elements = []
    idx = 0
    
    # Just get all nodes
    for node in root.xpath("//node"):
        # Basic filters
        if node.get("enabled", "false") != "true":
            continue
            
        # Get the basics
        text = node.get("text", "").strip()
        desc = node.get("content-desc", "").strip()
        res_id = node.get("resource-id", "")
        clickable = node.get("clickable", "false") == "true"
        class_name = node.get("class", "")
        bounds = node.get("bounds", "")
        
        # Must have SOME label
        label = text or desc
        if not label and res_id and "/" in res_id:
            # Make label from resource ID
            label = res_id.split("/")[-1].replace("_", " ").replace("-", " ").title()
        
        if not label:
            continue
            
        # Determine if it's interactive
        is_input = "edittext" in class_name.lower()
        is_button = "button" in class_name.lower()
        is_interactive = clickable or is_input or is_button
        
        if not is_interactive:
            continue
            
        # Determine action type
        if is_input:
            action = "type"
        elif is_button or clickable:
            action = "tap"
        else:
            action = "interact"
            
        # Simple element
        element = {
            "id": idx,
            "label": label,
            "action": action
        }
        
        # Add type hint for common patterns
        label_lower = label.lower()
        if any(x in label_lower for x in ["password", "pwd"]):
            element["hint"] = "password_field"
        elif any(x in label_lower for x in ["email", "mail"]):
            element["hint"] = "email_field"
        elif any(x in label_lower for x in ["username", "user name", "user"]):
            element["hint"] = "username_field"
        elif any(x in label_lower for x in ["search", "find"]):
            element["hint"] = "search_field"
        elif any(x in label_lower for x in ["login", "sign in", "signin", "log in"]):
            element["hint"] = "login_button"
        elif any(x in label_lower for x in ["submit", "done", "ok", "confirm"]):
            element["hint"] = "submit_button"
        elif any(x in label_lower for x in ["cancel", "close", "back"]):
            element["hint"] = "cancel_button"
            
        elements.append(element)
        idx += 1
    
    # Group by action type
    grouped = {
        "inputs": [e for e in elements if e["action"] == "type"],
        "buttons": [e for e in elements if e["action"] == "tap"],
        "all": elements
    }
    
    # Quick analysis
    analysis = {
        "has_form": len(grouped["inputs"]) >= 2,
        "has_login": any(e.get("hint", "").startswith("login") for e in elements),
        "total_interactive": len(elements)
    }
    
    return {
        "elements": grouped,
        "analysis": analysis,
        "instructions": _generate_instructions(grouped, analysis)
    }


def _generate_instructions(grouped: Dict, analysis: Dict) -> List[str]:
    """Generate simple instructions for common scenarios"""
    instructions = []
    
    if analysis["has_form"]:
        instructions.append("This appears to be a form. Fill inputs before submitting.")
        
    if analysis["has_login"]:
        # Find login-related elements
        username = next((e for e in grouped["all"] if e.get("hint") == "username_field"), None)
        password = next((e for e in grouped["all"] if e.get("hint") == "password_field"), None)
        login_btn = next((e for e in grouped["all"] if e.get("hint") == "login_button"), None)
        
        if username and password and login_btn:
            instructions.append(f"To login: type in {username['id']}, then {password['id']}, then tap {login_btn['id']}")
    
    return instructions