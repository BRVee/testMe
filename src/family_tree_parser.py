"""
Family tree parser - maintains parent-child relationships for UI elements
"""
from lxml import etree
from typing import Dict, List, Any, Optional
import re


def parse_family_tree(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI into a family tree structure showing relationships.
    Groups related elements together (e.g., form fields under their container).
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Build the family tree
    family_tree = {
        "families": [],
        "orphans": [],  # Elements without clear family
        "quick_index": {}  # id -> element mapping for fast lookup
    }
    
    # Process the root to build families
    _process_node_family(root, None, family_tree)
    
    # Post-process to create clean structure
    result = {
        "families": family_tree["families"],
        "orphans": family_tree["orphans"],
        "total_elements": len(family_tree["quick_index"]),
        "family_guide": _create_family_guide(family_tree["families"])
    }
    
    return result


def _process_node_family(node, parent_context: Optional[Dict], family_tree: Dict, depth: int = 0):
    """Recursively process nodes to identify families"""
    # Get node info
    text = node.get("text", "").strip()
    desc = node.get("content-desc", "").strip()
    res_id = node.get("resource-id", "")
    clickable = node.get("clickable", "false") == "true"
    enabled = node.get("enabled", "false") == "true"
    class_name = node.get("class", "")
    bounds = node.get("bounds", "")
    
    # Skip disabled elements
    if not enabled:
        for child in node:
            _process_node_family(child, parent_context, family_tree, depth + 1)
        return
    
    # Create label
    label = text or desc
    if not label and res_id and "/" in res_id:
        label = res_id.split("/")[-1].replace("_", " ").replace("-", " ").title()
    
    # Determine element type
    elem_type = _get_element_type(class_name, clickable)
    is_container = elem_type in ["container", "list", "form"]
    is_interactive = elem_type in ["input", "button"] or (clickable and label)
    
    current_element = None
    current_context = parent_context
    
    # Check if this is a family head (container with meaningful label)
    if is_container and label and len(node) > 0:
        # This is a family container
        family = {
            "name": label,
            "type": elem_type,
            "members": []
        }
        
        # Process all children as family members
        for child in node:
            _process_node_family(child, family, family_tree, depth + 1)
        
        # Only add family if it has interactive members
        if family["members"]:
            family_tree["families"].append(family)
            current_context = None  # Reset context after family
            
    elif is_interactive and label:
        # This is an interactive element
        elem_id = len(family_tree["quick_index"])
        
        # Determine action
        if elem_type == "input":
            action = "type"
        elif elem_type == "button" or clickable:
            action = "tap"
        else:
            action = "interact"
            
        element = {
            "id": elem_id,
            "label": label,
            "action": action,
            "type": elem_type
        }
        
        # Add hints for common patterns
        label_lower = label.lower()
        if any(x in label_lower for x in ["mobile", "phone", "number"]):
            element["hint"] = "phone_input"
        elif any(x in label_lower for x in ["password", "pwd"]):
            element["hint"] = "password_input"
        elif any(x in label_lower for x in ["email", "mail"]):
            element["hint"] = "email_input"
        elif any(x in label_lower for x in ["sign up", "signup", "register"]):
            element["hint"] = "signup_action"
        elif any(x in label_lower for x in ["login", "sign in"]):
            element["hint"] = "login_action"
        elif any(x in label_lower for x in ["otp", "code", "verification"]):
            element["hint"] = "otp_input"
            
        # Add to quick index
        family_tree["quick_index"][elem_id] = element
        
        # Add to parent family or orphans
        if parent_context and "members" in parent_context:
            parent_context["members"].append(element)
        else:
            # Look for semantic parent from recent text
            semantic_parent = _find_semantic_parent(node, family_tree["families"])
            if semantic_parent:
                semantic_parent["members"].append(element)
            else:
                family_tree["orphans"].append(element)
                
        current_element = element
    
    # Process children with current context
    for child in node:
        _process_node_family(child, current_context, family_tree, depth + 1)


def _get_element_type(class_name: str, clickable: bool) -> str:
    """Determine element type"""
    class_lower = class_name.lower()
    
    if "edittext" in class_lower:
        return "input"
    elif "button" in class_lower:
        return "button"
    elif "textview" in class_lower and clickable:
        return "button"  # Clickable text acts as button
    elif "textview" in class_lower:
        return "text"
    elif any(x in class_lower for x in ["recyclerview", "listview"]):
        return "list"
    elif any(x in class_lower for x in ["linearlayout", "relativelayout", "framelayout"]) and class_lower.count("layout") > 1:
        return "form"  # Multiple layouts often indicate form
    elif any(x in class_lower for x in ["viewgroup", "layout"]):
        return "container"
    else:
        return "element"


def _find_semantic_parent(node, existing_families: List[Dict]) -> Optional[Dict]:
    """Try to find a semantic parent for orphaned elements"""
    # Look at previous siblings for context
    parent = node.getparent()
    if parent is None:
        return None
        
    # Check recent text nodes that might be labels
    for i, sibling in enumerate(parent):
        if sibling == node:
            # Look at previous siblings
            for j in range(max(0, i-3), i):
                prev_sibling = parent[j]
                prev_text = prev_sibling.get("text", "").strip()
                
                # Check if this text matches any family name
                if prev_text:
                    for family in existing_families:
                        if prev_text.lower() in family["name"].lower() or family["name"].lower() in prev_text.lower():
                            return family
                            
    return None


def _create_family_guide(families: List[Dict]) -> Dict[str, Any]:
    """Create a guide showing relationships and common patterns"""
    guide = {
        "forms": [],
        "actions": [],
        "suggestions": []
    }
    
    for family in families:
        # Identify forms (families with input fields)
        has_inputs = any(m.get("type") == "input" for m in family["members"])
        has_button = any(m.get("type") == "button" for m in family["members"])
        
        if has_inputs:
            form_info = {
                "family_name": family["name"],
                "fields": [m for m in family["members"] if m.get("type") == "input"],
                "submit_button": next((m for m in family["members"] if m.get("type") == "button"), None)
            }
            guide["forms"].append(form_info)
            
            # Generate suggestion
            if form_info["submit_button"]:
                field_ids = [str(f["id"]) for f in form_info["fields"]]
                suggestion = f"To complete '{family['name']}': fill fields {', '.join(field_ids)}, then tap {form_info['submit_button']['id']}"
                guide["suggestions"].append(suggestion)
        
        # Collect all action buttons
        for member in family["members"]:
            if member.get("type") == "button":
                guide["actions"].append({
                    "id": member["id"],
                    "label": member["label"],
                    "family": family["name"]
                })
    
    return guide