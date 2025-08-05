from lxml import etree
from typing import List, Dict, Any
from pathlib import Path


def parse(xml_path: str) -> List[Dict[str, Any]]:
    """
    Parse Android UI XML dump into a clean JSON list of nodes.
    
    Returns list of dicts with keys:
    - resource-id
    - text
    - content-desc
    - clickable
    - bounds
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    nodes = []
    
    # Traverse all nodes
    for node in root.xpath("//node"):
        node_info = {
            "resource-id": node.get("resource-id", ""),
            "text": node.get("text", ""),
            "content-desc": node.get("content-desc", ""),
            "clickable": node.get("clickable", "false") == "true",
            "bounds": node.get("bounds", "")
        }
        
        # Only include nodes that have some identifying information
        if node_info["resource-id"] or node_info["text"] or node_info["content-desc"]:
            nodes.append(node_info)
    
    return nodes