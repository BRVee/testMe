import pytest
from pathlib import Path
import tempfile
from src.parser import parse


def test_parse_basic():
    """Test parsing basic UI XML with clickable nodes"""
    xml_content = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node resource-id="com.example:id/button1" 
        text="Login" 
        content-desc="" 
        clickable="true" 
        bounds="[100,200][300,400]"/>
  <node resource-id="" 
        text="Welcome" 
        content-desc="Welcome message" 
        clickable="false" 
        bounds="[0,0][500,100]"/>
  <node resource-id="com.example:id/input" 
        text="" 
        content-desc="Username field" 
        clickable="true" 
        bounds="[100,500][400,600]"/>
</hierarchy>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_path = f.name
    
    try:
        nodes = parse(temp_path)
        
        assert len(nodes) == 3
        
        # Check first node
        assert nodes[0]["resource-id"] == "com.example:id/button1"
        assert nodes[0]["text"] == "Login"
        assert nodes[0]["content-desc"] == ""
        assert nodes[0]["clickable"] is True
        assert nodes[0]["bounds"] == "[100,200][300,400]"
        
        # Check second node
        assert nodes[1]["clickable"] is False
        
        # Check third node
        assert nodes[2]["content-desc"] == "Username field"
        assert nodes[2]["clickable"] is True
        
    finally:
        Path(temp_path).unlink()


def test_parse_empty_nodes():
    """Test that nodes without any identifiers are filtered out"""
    xml_content = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node resource-id="" text="" content-desc="" clickable="false" bounds="[0,0][100,100]"/>
  <node resource-id="com.example:id/valid" text="" content-desc="" clickable="true" bounds="[0,0][100,100]"/>
</hierarchy>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_path = f.name
    
    try:
        nodes = parse(temp_path)
        # Only the second node should be included
        assert len(nodes) == 1
        assert nodes[0]["resource-id"] == "com.example:id/valid"
    finally:
        Path(temp_path).unlink()