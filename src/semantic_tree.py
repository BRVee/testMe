"""
Semantic tree parser - Groups UI elements by their semantic relationships
"""
from lxml import etree
from typing import Dict, List, Any, Optional, Tuple
import re


def build_tree(xml_str: str) -> Dict[str, Any]:
    """
    Build semantic tree from XML string.
    Groups labels with their nearest inputs and maintains parent-child relationships.
    """
    root = etree.fromstring(xml_str.encode('utf-8'))
    
    # Pass 1: Build real tree structure
    tree_root = _build_node_tree(root)
    
    # Pass 2: Add synthetic form groups
    _create_form_groups(tree_root)
    
    # Pass 3: Prune and clean
    _prune_tree(tree_root)
    
    return {
        "screen": tree_root
    }


def _build_node_tree(node) -> Dict[str, Any]:
    """Build tree maintaining XML parent-child relationships"""
    # Extract attributes
    attrs = dict(node.attrib)
    
    # Parse bounds
    bounds = _parse_bounds(attrs.get("bounds", "[0,0][0,0]"))
    
    # Build node
    tree_node = {
        "type": _get_semantic_type(attrs),
        "bounds": bounds
    }
    
    # Add important attributes
    if attrs.get("text"):
        tree_node["text"] = attrs["text"]
    if attrs.get("content-desc"):
        tree_node["contentDesc"] = attrs["content-desc"]
    if attrs.get("resource-id"):
        tree_node["resourceId"] = attrs["resource-id"]
    if attrs.get("clickable") == "true":
        tree_node["clickable"] = True
    if attrs.get("class"):
        tree_node["className"] = attrs["class"]
    
    # Process children
    children = []
    for child in node:
        child_node = _build_node_tree(child)
        if child_node:  # Skip empty nodes
            children.append(child_node)
    
    if children:
        tree_node["children"] = children
    
    return tree_node


def _get_semantic_type(attrs: Dict[str, str]) -> str:
    """Determine semantic type of element"""
    class_name = attrs.get("class", "").lower()
    clickable = attrs.get("clickable") == "true"
    text = attrs.get("text", "")
    
    if "edittext" in class_name or "textinput" in class_name:
        return "input"
    elif "button" in class_name or (clickable and text):
        return "button"
    elif "textview" in class_name and not clickable:
        return "label"
    elif "checkbox" in class_name:
        return "checkbox"
    elif "switch" in class_name:
        return "switch"
    elif "imageview" in class_name and clickable:
        return "imageButton"
    elif any(x in class_name for x in ["layout", "viewgroup", "view"]):
        return "container"
    else:
        return "element"


def _parse_bounds(bounds_str: str) -> List[int]:
    """Parse bounds string to [x1, y1, x2, y2]"""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if match:
        return [int(x) for x in match.groups()]
    return [0, 0, 0, 0]


def _create_form_groups(node: Dict[str, Any]):
    """Create synthetic form groups by pairing labels with inputs"""
    if node.get("type") == "container" and node.get("children"):
        # Find labels and inputs in this container
        labels = []
        inputs = []
        other_children = []
        
        for child in node["children"]:
            if child["type"] == "label" and child.get("text"):
                labels.append(child)
            elif child["type"] == "input":
                inputs.append(child)
            else:
                # Recursively process other containers
                if child.get("children"):
                    _create_form_groups(child)
                other_children.append(child)
        
        # Pair labels with nearby inputs
        new_children = []
        used_inputs = set()
        
        for label in labels:
            nearest_input = _find_nearest_input(label, inputs, used_inputs)
            if nearest_input:
                # Create form group
                form_group = {
                    "type": "formGroup",
                    "bounds": _merge_bounds(label["bounds"], nearest_input["bounds"]),
                    "label": label.get("text", ""),
                    "input": {
                        "type": "input",
                        "bounds": nearest_input["bounds"]
                    }
                }
                
                # Copy input attributes
                if nearest_input.get("resourceId"):
                    form_group["input"]["resourceId"] = nearest_input["resourceId"]
                if nearest_input.get("text"):
                    form_group["input"]["hint"] = nearest_input["text"]
                
                new_children.append(form_group)
                used_inputs.add(id(nearest_input))
            else:
                # Keep label as-is if no matching input
                new_children.append(label)
        
        # Add remaining inputs
        for inp in inputs:
            if id(inp) not in used_inputs:
                new_children.append(inp)
        
        # Add other children
        new_children.extend(other_children)
        
        # Update children
        node["children"] = new_children
    
    # Process children recursively
    if node.get("children"):
        for child in node["children"]:
            _create_form_groups(child)


def _find_nearest_input(label: Dict, inputs: List[Dict], used: set) -> Optional[Dict]:
    """Find the nearest input below the label"""
    if not inputs:
        return None
    
    label_bounds = label["bounds"]
    min_distance = float('inf')
    nearest = None
    
    for inp in inputs:
        if id(inp) in used:
            continue
            
        inp_bounds = inp["bounds"]
        
        # Check if input is below label (y1 of input > y2 of label)
        if inp_bounds[1] > label_bounds[3]:
            # Calculate vertical distance
            distance = inp_bounds[1] - label_bounds[3]
            
            # Also check horizontal alignment
            label_center_x = (label_bounds[0] + label_bounds[2]) / 2
            inp_center_x = (inp_bounds[0] + inp_bounds[2]) / 2
            x_distance = abs(label_center_x - inp_center_x)
            
            # Prefer vertically close and horizontally aligned
            if distance < 100 and x_distance < 200:  # Thresholds
                total_distance = distance + x_distance * 0.5
                if total_distance < min_distance:
                    min_distance = total_distance
                    nearest = inp
    
    return nearest


def _merge_bounds(b1: List[int], b2: List[int]) -> List[int]:
    """Merge two bounds to encompass both"""
    return [
        min(b1[0], b2[0]),
        min(b1[1], b2[1]),
        max(b1[2], b2[2]),
        max(b1[3], b2[3])
    ]


def _prune_tree(node: Dict[str, Any]):
    """Remove unnecessary attributes and empty containers"""
    # Remove empty containers
    if node.get("type") == "container" and node.get("children"):
        # Filter out empty containers
        node["children"] = [
            child for child in node["children"]
            if not (child.get("type") == "container" and 
                   not child.get("children") and
                   not child.get("text") and
                   not child.get("clickable"))
        ]
        
        # Flatten single-child containers
        if len(node["children"]) == 1 and node.get("type") == "container":
            child = node["children"][0]
            # Preserve bounds from parent if child doesn't have them
            if not child.get("bounds") or child["bounds"] == [0, 0, 0, 0]:
                child["bounds"] = node.get("bounds", [0, 0, 0, 0])
    
    # Recursively prune children
    if node.get("children"):
        for child in node["children"]:
            _prune_tree(child)
        
        # Remove empty children list
        if not node["children"]:
            del node["children"]
    
    # Remove className if not needed
    if node.get("className") and node.get("type") != "element":
        del node["className"]


# For testing
if __name__ == "__main__":
    # Test with sample XML
    test_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node index="0" class="android.widget.FrameLayout" clickable="false" enabled="true" bounds="[0,0][1080,2340]">
        <node index="0" class="android.widget.LinearLayout" clickable="false" enabled="true" bounds="[0,100][1080,800]">
          <node index="0" text="Email" class="android.widget.TextView" clickable="false" enabled="true" bounds="[50,150][200,200]"/>
          <node index="1" text="" resource-id="com.app:id/email" class="android.widget.EditText" clickable="true" enabled="true" bounds="[50,220][1030,320]"/>
          <node index="2" text="Password" class="android.widget.TextView" clickable="false" enabled="true" bounds="[50,350][200,400]"/>
          <node index="3" text="" resource-id="com.app:id/password" class="android.widget.EditText" clickable="true" enabled="true" bounds="[50,420][1030,520]"/>
        </node>
        <node index="1" text="LOGIN" resource-id="com.app:id/loginBtn" class="android.widget.Button" clickable="true" enabled="true" bounds="[100,600][980,700]"/>
      </node>
    </hierarchy>"""
    
    result = build_tree(test_xml)
    import json
    print(json.dumps(result, indent=2))