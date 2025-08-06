"""
Fast tree parser that maintains parent-child relationships
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Set


def parse_fast_tree(xml_path: str) -> Dict[str, Any]:
    """
    Fast parser that maintains parent-child tree structure.
    Captures ALL visible text while keeping relationships clear.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Track seen text to avoid duplication
    seen_texts = set()
    element_id = [0]
    
    # Build tree
    result = _build_tree(root, seen_texts, element_id)
    
    # Clean up the tree by removing duplicate texts
    _deduplicate_tree(result, set())
    
    return {
        "screen": result,
        "total_elements": element_id[0]
    }


def _build_tree(node, seen_texts: Set[str], element_id: List[int]) -> Optional[Dict[str, Any]]:
    """Build tree node maintaining parent-child relationships"""
    # Skip disabled elements
    if node.get('enabled', 'true') != 'true':
        return None
    
    # Get basic attributes
    text = node.get('text', '').strip()
    desc = node.get('content-desc', '').strip()
    res_id = node.get('resource-id', '')
    clickable = node.get('clickable') == 'true'
    class_name = node.get('class', '')
    bounds = node.get('bounds', '')
    
    # Get visible text
    visible_text = text or desc
    
    # Determine node type
    node_type = _get_type(class_name, clickable)
    
    # Check if this is just a container with no meaningful content
    is_container = node_type in ['container', 'layout']
    
    # Build current node
    current = {
        "id": element_id[0],
        "type": node_type,
        "text": visible_text
    }
    
    element_id[0] += 1
    
    # Add essential attributes
    if clickable or node_type in ['input', 'button']:
        if node_type == 'input':
            current["action"] = "type"
        else:
            current["action"] = "tap"
    
    if res_id:
        current["resourceId"] = res_id
    
    # Process children
    children = []
    for child in node:
        child_node = _build_tree(child, seen_texts, element_id)
        if child_node:
            children.append(child_node)
    
    # Add children if any
    if children:
        current["children"] = children
    
    # Skip empty containers that add no value
    if is_container and not visible_text and len(children) == 1:
        # Return the single child directly
        return children[0]
    
    # Skip completely empty nodes
    if not visible_text and not children and not current.get("action"):
        return None
    
    return current


def _get_type(class_name: str, clickable: bool) -> str:
    """Determine element type"""
    class_lower = class_name.lower()
    
    if 'edittext' in class_lower:
        return 'input'
    elif 'button' in class_lower:
        return 'button'
    elif 'textview' in class_lower and clickable:
        return 'button'
    elif 'textview' in class_lower:
        return 'text'
    elif 'imageview' in class_lower and clickable:
        return 'button'
    elif any(x in class_lower for x in ['recyclerview', 'listview']):
        return 'list'
    elif any(x in class_lower for x in ['linearlayout', 'relativelayout', 'framelayout', 'viewgroup']):
        return 'container'
    else:
        return 'element'


def _deduplicate_tree(node: Dict[str, Any], seen: Set[str]) -> bool:
    """Remove duplicate texts from tree, return True if node should be kept"""
    if not node:
        return False
        
    text = node.get("text", "")
    
    # Check if we should keep this node
    if text and text in seen and node.get("type") == "text":
        # Skip duplicate text nodes
        return False
    
    if text:
        seen.add(text)
    
    # Process children
    if node.get("children"):
        new_children = []
        for child in node["children"]:
            if _deduplicate_tree(child, seen):
                new_children.append(child)
        node["children"] = new_children
        
        # Remove empty children list
        if not node["children"]:
            del node["children"]
    
    return True


def get_family_tree(tree: Dict[str, Any]) -> Dict[str, Any]:
    """Extract family tree showing clear parent-child relationships"""
    relationships = []
    
    def find_label_input_pairs(node):
        """Find label-input pairs within containers"""
        children = node.get("children", [])
        
        # Look for consecutive label-input pairs
        i = 0
        while i < len(children):
            child = children[i]
            
            # Check if this is a text label followed by an input
            if (child.get("type") == "text" and 
                child.get("text") and
                i + 1 < len(children) and
                children[i + 1].get("type") == "input"):
                
                # Found a label-input pair
                relationships.append({
                    "label": child["text"],
                    "input": children[i + 1].get("resourceId", f"input-{children[i + 1].get('id', '')}"),
                    "relationship": "label_for_input"
                })
                i += 2  # Skip both
            else:
                # Process this node normally
                if child.get("text"):
                    # Find parent text
                    parent_text = node.get("text", "")
                    if not parent_text:
                        # Look up the tree for a meaningful parent
                        parent_text = "Screen"
                    
                    if parent_text and parent_text != child.get("text"):
                        relationships.append({
                            "parent": parent_text,
                            "child": child["text"],
                            "relationship": "contains"
                        })
                
                # Recursively process children
                find_label_input_pairs(child)
                i += 1
        
        # Don't double-process containers, they're already handled above
    
    # Start from root
    find_label_input_pairs(tree)
    
    # Also extract top-level relationships
    def extract_hierarchy(node, parent_text="Screen"):
        """Extract hierarchical relationships"""
        node_text = node.get("text", "")
        
        # Add relationship if this node has meaningful text
        if node_text and node_text != parent_text and node.get("type") != "container":
            found = False
            # Check if already in relationships
            for rel in relationships:
                if (rel.get("child") == node_text or 
                    rel.get("label") == node_text):
                    found = True
                    break
            
            if not found:
                relationships.append({
                    "parent": parent_text,
                    "child": node_text,
                    "relationship": "contains"
                })
        
        # Process children with this node as parent
        effective_parent = node_text if node_text else parent_text
        for child in node.get("children", []):
            extract_hierarchy(child, effective_parent)
    
    # Extract top-level relationships
    if tree.get("children"):
        for child in tree["children"]:
            extract_hierarchy(child)
    
    return {
        "relationships": relationships
    }