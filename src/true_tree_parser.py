"""
True tree parser - Maintains actual parent-child hierarchy from XML
"""
from lxml import etree
from typing import Dict, List, Any, Optional
import re


def parse_true_tree(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI maintaining the true parent-child tree structure.
    Captures ALL visible text while preserving hierarchy.
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Build the tree starting from root
    ui_tree = _build_tree_node(root, element_id=[0])
    
    # Create flat index for quick lookup
    flat_index = {}
    _build_flat_index(ui_tree, flat_index)
    
    # Analyze the tree for patterns
    analysis = _analyze_tree(ui_tree, flat_index)
    
    return {
        "tree": ui_tree,
        "flat_index": flat_index,
        "analysis": analysis,
        "total_elements": len(flat_index)
    }


def _build_tree_node(node, element_id: List[int], parent_path: str = "") -> Optional[Dict]:
    """Recursively build tree node with all children"""
    # Get node attributes
    text = node.get("text", "").strip()
    desc = node.get("content-desc", "").strip()
    res_id = node.get("resource-id", "")
    clickable = node.get("clickable", "false") == "true"
    enabled = node.get("enabled", "false") == "true"
    class_name = node.get("class", "")
    bounds = node.get("bounds", "")
    
    # Determine visibility
    visible_text = text or desc
    if not visible_text and res_id and "/" in res_id:
        id_part = res_id.split("/")[-1]
        if not any(x in id_part.lower() for x in ["layout", "container", "view", "group", "root"]):
            visible_text = id_part.replace("_", " ").replace("-", " ").title()
    
    # Determine type
    elem_type = _get_type(class_name, clickable)
    
    # Skip pure containers with no identity unless they have children
    is_container = elem_type in ["container", "layout"]
    has_children = len(node) > 0
    
    if not visible_text and is_container and not has_children:
        # Skip empty containers
        return None
    
    # Build current node
    current_node = {
        "id": element_id[0],
        "type": elem_type,
        "text": visible_text or f"[{elem_type}]",
        "original_text": text,
        "content_desc": desc,
        "clickable": clickable,
        "enabled": enabled,
        "path": parent_path + f"/{elem_type}[{element_id[0]}]",
        "children": []
    }
    
    # Add action if interactive
    if clickable or elem_type in ["input", "button"]:
        if elem_type == "input":
            current_node["action"] = "type"
        else:
            current_node["action"] = "tap"
    
    # Add bounds if present
    if bounds and bounds != "[0,0][0,0]":
        current_node["bounds"] = bounds
    
    # Increment ID for next element
    element_id[0] += 1
    
    # Process all children
    for child in node:
        child_node = _build_tree_node(child, element_id, current_node["path"])
        if child_node:
            current_node["children"].append(child_node)
    
    # If this is a container with only one visible child, merge them
    if (is_container and not visible_text and 
        len(current_node["children"]) == 1 and 
        not current_node["clickable"]):
        # Return the child directly to flatten unnecessary nesting
        child = current_node["children"][0]
        child["parent_was_container"] = True
        return child
    
    return current_node


def _get_type(class_name: str, clickable: bool) -> str:
    """Determine element type"""
    class_lower = class_name.lower()
    
    if "edittext" in class_lower:
        return "input"
    elif "button" in class_lower:
        return "button"
    elif "textview" in class_lower and clickable:
        return "clickable_text"
    elif "textview" in class_lower:
        return "text"
    elif "imageview" in class_lower and clickable:
        return "image_button"
    elif "imageview" in class_lower:
        return "image"
    elif "checkbox" in class_lower:
        return "checkbox"
    elif "switch" in class_lower:
        return "switch"
    elif any(x in class_lower for x in ["recyclerview", "listview"]):
        return "list"
    elif any(x in class_lower for x in ["linearlayout", "relativelayout", "framelayout"]):
        return "layout"
    elif any(x in class_lower for x in ["viewgroup", "view"]):
        return "container"
    else:
        return "element"


def _build_flat_index(node: Dict, index: Dict):
    """Build flat index of all nodes for quick lookup"""
    if node:
        index[node["id"]] = node
        for child in node.get("children", []):
            _build_flat_index(child, index)


def _analyze_tree(tree: Dict, flat_index: Dict) -> Dict[str, Any]:
    """Analyze the tree to find patterns and relationships"""
    analysis = {
        "forms": [],
        "clickable_elements": [],
        "text_elements": [],
        "relationships": []
    }
    
    # Find all elements by type
    for elem_id, elem in flat_index.items():
        if elem.get("action") == "type":
            # Input field - look for associated label
            label = _find_label_for_input(elem, tree)
            form_group = _find_form_container(elem, tree)
            
            analysis["forms"].append({
                "input_id": elem_id,
                "input_text": elem["text"],
                "label": label,
                "form_group": form_group
            })
        
        if elem.get("clickable"):
            analysis["clickable_elements"].append({
                "id": elem_id,
                "text": elem["text"],
                "type": elem["type"],
                "action": elem.get("action", "tap")
            })
        
        if elem["type"] == "text" and not elem.get("clickable"):
            analysis["text_elements"].append({
                "id": elem_id,
                "text": elem["text"]
            })
    
    # Find parent-child relationships for clickables
    for elem_id, elem in flat_index.items():
        if elem.get("clickable") and elem.get("children"):
            # This clickable has children
            child_texts = []
            _collect_child_texts(elem, child_texts)
            if child_texts:
                analysis["relationships"].append({
                    "parent_id": elem_id,
                    "parent_text": elem["text"],
                    "contains_texts": child_texts,
                    "relationship": "contains"
                })
    
    return analysis


def _find_label_for_input(input_elem: Dict, tree: Dict) -> Optional[str]:
    """Find text label for an input field by checking siblings and parent"""
    # Strategy 1: Check immediate siblings in parent
    parent = _find_parent_of(input_elem["id"], tree)
    if parent:
        for i, child in enumerate(parent["children"]):
            if child["id"] == input_elem["id"] and i > 0:
                # Check previous sibling
                prev_sibling = parent["children"][i - 1]
                if prev_sibling["type"] == "text":
                    return prev_sibling["text"]
    
    # Strategy 2: Check if input has text children
    child_texts = []
    _collect_child_texts(input_elem, child_texts, max_depth=1)
    if child_texts:
        return " ".join(child_texts)
    
    # Strategy 3: Use the input's own text if meaningful
    if input_elem["text"] and input_elem["text"] != "[input]":
        return input_elem["text"]
    
    return None


def _find_form_container(elem: Dict, tree: Dict) -> Optional[str]:
    """Find the form container this element belongs to"""
    parent = _find_parent_of(elem["id"], tree)
    while parent:
        # Check if parent has multiple inputs (likely a form)
        input_count = sum(1 for child in _get_all_descendants(parent) 
                         if child.get("action") == "type")
        if input_count >= 2:
            return parent["text"] if parent["text"] != f"[{parent['type']}]" else "Form"
        parent = _find_parent_of(parent["id"], tree)
    return None


def _find_parent_of(elem_id: int, tree: Dict) -> Optional[Dict]:
    """Find parent node of given element ID"""
    def search(node: Dict) -> Optional[Dict]:
        for child in node.get("children", []):
            if child["id"] == elem_id:
                return node
            result = search(child)
            if result:
                return result
        return None
    
    return search(tree)


def _get_all_descendants(node: Dict) -> List[Dict]:
    """Get all descendants of a node"""
    descendants = []
    for child in node.get("children", []):
        descendants.append(child)
        descendants.extend(_get_all_descendants(child))
    return descendants


def _collect_child_texts(node: Dict, texts: List[str], max_depth: int = 3, current_depth: int = 0):
    """Collect all text from children up to max depth"""
    if current_depth >= max_depth:
        return
    
    for child in node.get("children", []):
        if child["type"] == "text" and child["text"] != f"[{child['type']}]":
            texts.append(child["text"])
        _collect_child_texts(child, texts, max_depth, current_depth + 1)