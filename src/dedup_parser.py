"""
Deduplicated parser - Removes redundant elements showing same text
"""
from lxml import etree
from typing import Dict, List, Any, Optional, Set, Tuple
import re


def parse_dedup_tree(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI with deduplication to show each unique text only once.
    Maintains hierarchy while removing redundant elements.
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Track what we've seen
    seen_texts = {}  # text -> first occurrence info
    element_id = [0]
    
    # Build deduplicated tree
    dedup_tree = _build_dedup_node(root, seen_texts, element_id)
    
    # If no tree was built, try a simpler approach
    if not dedup_tree:
        # Fallback: just get all visible elements
        all_elements = []
        for node in root.xpath("//node"):
            # Check if enabled
            if node.get("enabled", "true") != "true":
                continue
                
            text = node.get("text", "").strip()
            desc = node.get("content-desc", "").strip()
            visible_text = text or desc
            
            if visible_text and visible_text.lower() not in seen_texts:
                elem = {
                    "id": len(all_elements),
                    "text": visible_text,
                    "type": _get_element_type(node.get("class", ""), node.get("clickable") == "true")
                }
                
                if node.get("clickable") == "true" or elem["type"] == "input":
                    elem["action"] = "type" if elem["type"] == "input" else "tap"
                
                all_elements.append(elem)
                seen_texts[visible_text.lower()] = True
        
        # Create structure from flat list
        return {
            "screen": _organize_by_function(all_elements),
            "total": len(all_elements)
        }
    
    # Create a clean, minimal structure
    clean_structure = _create_clean_structure(dedup_tree)
    
    return clean_structure


def _build_dedup_node(node, seen_texts: Dict, element_id: List[int], 
                      parent_clickable: bool = False) -> Optional[Dict]:
    """Build node while deduplicating text"""
    # Get attributes
    text = node.get("text", "").strip()
    desc = node.get("content-desc", "").strip()
    res_id = node.get("resource-id", "")
    clickable = node.get("clickable", "false") == "true"
    enabled = node.get("enabled", "false") == "true"
    class_name = node.get("class", "")
    bounds = node.get("bounds", "")
    
    # Skip disabled
    if not enabled:
        return None
    
    # Get visible text
    visible_text = text or desc
    
    # Determine type
    elem_type = _get_element_type(class_name, clickable)
    is_container = elem_type in ["container", "layout", "list"]
    
    # Skip containers with no text unless they're clickable
    if is_container and not visible_text and not clickable:
        # Process children directly
        children = []
        for child in node:
            child_node = _build_dedup_node(child, seen_texts, element_id, parent_clickable or clickable)
            if child_node:
                children.append(child_node)
        
        # If container has only one child, return the child directly
        if len(children) == 1:
            return children[0]
        elif len(children) > 1:
            # Create a group node
            return {
                "id": element_id[0],
                "type": "group",
                "children": children
            }
        else:
            return None
    
    # Check for duplicate text (but keep if it's clickable and previous wasn't)
    if visible_text:
        text_key = visible_text.lower()
        
        if text_key in seen_texts:
            prev_info = seen_texts[text_key]
            # Keep this one only if:
            # 1. This is clickable and previous wasn't
            # 2. This is an input and previous wasn't
            if (clickable and not prev_info['clickable']) or \
               (elem_type == "input" and prev_info['type'] != "input"):
                # Replace the previous one
                pass
            else:
                # Skip this duplicate
                return None
        
        # Record this text
        seen_texts[text_key] = {
            'id': element_id[0],
            'clickable': clickable,
            'type': elem_type,
            'bounds': bounds
        }
    elif not clickable and elem_type != "input":
        # No text and not interactive - skip
        return None
    
    # Build node
    current_node = {
        "id": element_id[0],
        "type": elem_type,
        "text": visible_text or f"[{elem_type}]"
    }
    
    element_id[0] += 1
    
    # Add properties only if needed
    if clickable or elem_type in ["input", "button"]:
        if elem_type == "input":
            current_node["action"] = "type"
        else:
            current_node["action"] = "tap"
    
    # Process children (but don't include them if this node already represents the interaction)
    if not clickable or elem_type == "container":
        children = []
        for child in node:
            child_node = _build_dedup_node(child, seen_texts, element_id, clickable)
            if child_node:
                children.append(child_node)
        
        if children:
            current_node["children"] = children
    
    return current_node


def _get_element_type(class_name: str, clickable: bool) -> str:
    """Determine element type"""
    class_lower = class_name.lower()
    
    if "edittext" in class_lower:
        return "input"
    elif "button" in class_lower:
        return "button"
    elif "textview" in class_lower and clickable:
        return "button"  # Clickable text is effectively a button
    elif "textview" in class_lower:
        return "text"
    elif "checkbox" in class_lower:
        return "checkbox"
    elif "switch" in class_lower:
        return "switch"
    elif any(x in class_lower for x in ["recyclerview", "listview"]):
        return "list"
    elif any(x in class_lower for x in ["layout", "viewgroup"]):
        return "container"
    else:
        return "element"


def _create_clean_structure(tree: Optional[Dict]) -> Dict[str, Any]:
    """Create a clean, minimal structure for LLM consumption"""
    if not tree:
        return {
            "screen": {
                "texts": [],
                "inputs": [],
                "actions": [],
                "forms": []
            },
            "total": 0
        }
    
    # Flatten tree into sections
    sections = []
    current_section = []
    
    def process_node(node, section):
        if node.get("type") == "group":
            # Start new section if current has items
            if section:
                sections.append(section)
                section = []
            
            # Process group children
            for child in node.get("children", []):
                process_node(child, section)
        else:
            # Add node to current section
            clean_node = {
                "id": node["id"],
                "text": node["text"],
                "type": node["type"]
            }
            
            if node.get("action"):
                clean_node["action"] = node["action"]
            
            section.append(clean_node)
            
            # Process children in same section
            for child in node.get("children", []):
                process_node(child, section)
        
        return section
    
    final_section = process_node(tree, current_section)
    if final_section:
        sections.append(final_section)
    
    # Merge small sections
    merged_sections = []
    current_merge = []
    
    for section in sections:
        if len(section) <= 2 and current_merge:
            # Merge with previous
            current_merge.extend(section)
        else:
            if current_merge:
                merged_sections.append(current_merge)
            current_merge = section
    
    if current_merge:
        merged_sections.append(current_merge)
    
    # Create final structure
    all_elements = []
    for i, section in enumerate(merged_sections):
        for elem in section:
            all_elements.append(elem)
    
    # Group by functionality
    result = {
        "screen": _organize_by_function(all_elements),
        "total": len(all_elements)
    }
    
    return result


def _organize_by_function(elements: List[Dict]) -> Dict[str, Any]:
    """Organize elements by their function"""
    organized = {
        "texts": [],
        "inputs": [],
        "actions": [],
        "forms": []
    }
    
    # First pass: categorize elements
    for elem in elements:
        if elem.get("action") == "type":
            organized["inputs"].append(elem)
        elif elem.get("action") == "tap":
            organized["actions"].append(elem)
        elif elem["type"] == "text":
            organized["texts"].append(elem)
    
    # Second pass: identify forms
    if organized["inputs"]:
        # Find related elements for each input
        for input_elem in organized["inputs"]:
            form = {
                "input": input_elem,
                "label": None,
                "submit": None
            }
            
            # Find label (text element with similar text)
            for text_elem in organized["texts"]:
                if _might_be_label_for(text_elem["text"], input_elem["text"]):
                    form["label"] = text_elem
                    break
            
            # Find submit button
            for action_elem in organized["actions"]:
                action_text = action_elem["text"].lower()
                if any(x in action_text for x in ["continue", "submit", "next", "done"]):
                    form["submit"] = action_elem
                    break
            
            organized["forms"].append(form)
    
    return organized


def _might_be_label_for(text: str, input_text: str) -> bool:
    """Check if text might be a label for input"""
    text_lower = text.lower()
    input_lower = input_text.lower()
    
    # Common patterns
    patterns = [
        "enter", "input", "type", "provide",
        "mobile", "phone", "email", "password",
        "name", "address", "code"
    ]
    
    return any(p in text_lower for p in patterns) or input_lower in text_lower