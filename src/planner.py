from typing import List, Dict, Any, Optional


def choose_node(nodes: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    LLM stub: Pick the first clickable node that has non-empty text.
    
    Returns selector dict with keys matching node identifiers
    (resource-id, text, content-desc).
    """
    for node in nodes:
        # Only consider clickable nodes
        if not node.get("clickable", False):
            continue
            
        # Pick first node with non-empty text
        if node.get("text"):
            return {
                "resource-id": node.get("resource-id", ""),
                "text": node.get("text", ""),
                "content-desc": node.get("content-desc", "")
            }
    
    # Fallback: pick first clickable node with any identifier
    for node in nodes:
        if not node.get("clickable", False):
            continue
            
        if node.get("resource-id") or node.get("content-desc"):
            return {
                "resource-id": node.get("resource-id", ""),
                "text": node.get("text", ""),
                "content-desc": node.get("content-desc", "")
            }
    
    return None