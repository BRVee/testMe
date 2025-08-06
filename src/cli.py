import click
import json
from pathlib import Path
import subprocess

from .android import dump_ui, tap_node
from .parser import parse, parse_for_llm, parse_minimal_for_llm, parse_hierarchical_for_llm
from .simple_parser import parse_ui_tree
from .ultra_simple_parser import parse_actionable_elements
from .family_tree_parser import parse_family_tree
from .clean_tree_parser import parse_clean_tree
from .complete_parser import parse_complete_ui
from .true_tree_parser import parse_true_tree
from .dedup_parser import parse_dedup_tree
from .semantic_tree import build_tree
from .fast_parser import parse_fast, parse_ultra_fast
from .fast_tree_parser import parse_fast_tree, get_family_tree
from .planner import choose_node


@click.group()
def cli():
    """QE-First: Zero-instrumentation Android UI driver"""
    pass


@cli.command()
def check():
    """Check ADB connection and device status"""
    try:
        from .android import check_adb_connection
        
        # Check if ADB is installed
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True)
            click.echo(f"✓ ADB installed: {result.stdout.strip().split('\\n')[0]}")
        except FileNotFoundError:
            click.echo("✗ ADB not found. Please install Android SDK Platform Tools.", err=True)
            click.echo("  Download from: https://developer.android.com/studio/releases/platform-tools", err=True)
            return
        
        # Check device connection
        if check_adb_connection():
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devices = [line for line in result.stdout.strip().split('\\n')[1:] if line.strip()]
            click.echo(f"✓ Device connected: {devices[0].split()[0]}")
            
            # Check if we can access shell
            result = subprocess.run(["adb", "shell", "echo", "test"], capture_output=True, text=True)
            if result.returncode == 0:
                click.echo("✓ ADB shell access: OK")
            else:
                click.echo("✗ ADB shell access: Failed", err=True)
        else:
            click.echo("✗ No Android device connected", err=True)
            click.echo("  1. Connect your Android device via USB", err=True)
            click.echo("  2. Enable Developer Options and USB Debugging", err=True)
            click.echo("  3. Accept the debugging authorization prompt on your device", err=True)
            
    except Exception as e:
        click.echo(f"Error checking ADB: {e}", err=True)


@cli.command()
def dump():
    """Dumps XML → window_dump.xml + prints JSON"""
    try:
        # Dump UI to XML
        xml_path = dump_ui()
        click.echo(f"Dumped UI to: {xml_path}")
        
        # Parse to JSON
        nodes = parse(xml_path)
        
        # Print JSON
        click.echo(json.dumps(nodes, indent=2))
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def plan():
    """Reads JSON, asks LLM, prints chosen node"""
    try:
        # Check if window_dump.xml exists
        xml_path = Path.cwd() / "window_dump.xml"
        if not xml_path.exists():
            click.echo("Error: window_dump.xml not found. Run 'qe dump' first.", err=True)
            raise click.Abort()
        
        # Parse XML
        nodes = parse(str(xml_path))
        
        # Choose node
        chosen = choose_node(nodes)
        
        if chosen:
            # Display chosen node info
            click.echo("Chosen node:")
            if chosen["text"]:
                click.echo(f"  Text: {chosen['text']}")
            if chosen["resource-id"]:
                click.echo(f"  Resource ID: {chosen['resource-id']}")
            if chosen["content-desc"]:
                click.echo(f"  Content Description: {chosen['content-desc']}")
            
            # Also print as JSON for debugging
            click.echo("\nSelector:")
            click.echo(json.dumps(chosen, indent=2))
        else:
            click.echo("No suitable clickable node found.", err=True)
            raise click.Abort()
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def run():
    """Performs the click (prompts Y/N first)"""
    try:
        # Check if window_dump.xml exists
        xml_path = Path.cwd() / "window_dump.xml"
        if not xml_path.exists():
            click.echo("Error: window_dump.xml not found. Run 'qe dump' first.", err=True)
            raise click.Abort()
        
        # Parse XML and choose node
        nodes = parse(str(xml_path))
        chosen = choose_node(nodes)
        
        if not chosen:
            click.echo("No suitable clickable node found.", err=True)
            raise click.Abort()
        
        # Display chosen node
        click.echo("Will click on:")
        if chosen["text"]:
            click.echo(f"  Text: {chosen['text']}")
        if chosen["resource-id"]:
            click.echo(f"  Resource ID: {chosen['resource-id']}")
        if chosen["content-desc"]:
            click.echo(f"  Content Description: {chosen['content-desc']}")
        
        # Prompt for confirmation
        if not click.confirm("Proceed?", default=False):
            click.echo("Aborted.")
            return
        
        # Perform tap
        tap_node(chosen)
        click.echo("Click performed successfully.")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


def _print_tree(node, indent=0):
    """Helper to print tree structure"""
    if not node:
        return
    
    # Print current node
    prefix = "  " * indent + ("└─ " if indent > 0 else "")
    text = node['text'][:50] + "..." if len(node['text']) > 50 else node['text']
    action = f" [{node['action'].upper()}]" if node.get('action') else ""
    click.echo(f"{prefix}[{node['id']}] {text}{action}")
    
    # Print children
    for child in node.get('children', []):
        _print_tree(child, indent + 1)


@cli.command()
def dump_llm():
    """Dumps UI in clean grouped format for LLM understanding"""
    try:
        # Dump UI to XML
        xml_path = dump_ui()
        click.echo(f"Dumped UI to: {xml_path}")
        
        # Use clean tree parser that groups related elements
        result = parse_clean_tree(xml_path)
        
        # Save to JSON file
        output_file = Path.cwd() / "dumpXMLtoJson.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        click.echo(f"\nClean dump saved to: {output_file}")
        click.echo(f"Total elements: {result['total']}")
        click.echo(f"Groups found: {len(result['groups'])}")
        
        # Display groups
        click.echo("\n📋 Element Groups:")
        for group in result['groups'][:5]:
            click.echo(f"\n  {group['title']} ({group['purpose']}):")
            for elem in group['elements'][:3]:
                action = f" [{elem['action'].upper()}]" if elem.get('action') else ""
                click.echo(f"    [{elem['id']}] {elem['label']}{action}")
                if elem.get('parent_context'):
                    click.echo(f"        Context: {elem['parent_context']}")
        
        if len(result['groups']) > 5:
            click.echo(f"\n  ... and {len(result['groups']) - 5} more groups")
        
        # Show quick actions
        click.echo("\n⚡ Quick Actions:")
        actions = [elem for elem in result['flat_list'] if elem.get('action')][:5]
        for elem in actions:
            click.echo(f"  [{elem['id']}] {elem['label']} → {elem['action'].upper()}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


def _display_fast_tree(node, indent=0, max_depth=4):
    """Display tree structure with indentation"""
    if not node or indent > max_depth:
        return
        
    prefix = "  " * indent + ("└─ " if indent > 0 else "")
    text = node.get('text', '')[:40]
    if len(node.get('text', '')) > 40:
        text += "..."
    
    node_type = node.get('type', 'unknown')
    action = f" [{node.get('action', '').upper()}]" if node.get('action') else ""
    res_id = f" ({node.get('resourceId', '')})" if node.get('resourceId') else ""
    
    # Show node
    click.echo(f"{prefix}{text}{action}{res_id}")
    
    # Show children
    for child in node.get('children', []):
        _display_fast_tree(child, indent + 1, max_depth)


def _display_tree_summary(node, indent=0):
    """Display a summary of the semantic tree"""
    prefix = "  " * indent
    
    # Display current node
    node_type = node.get("type", "unknown")
    if node_type == "formGroup":
        click.echo(f"{prefix}📋 Form Group: {node.get('label', 'Unlabeled')}")
        if node.get("input"):
            inp = node["input"]
            click.echo(f"{prefix}  └─ Input: {inp.get('resourceId', 'no-id')}")
    elif node_type == "button":
        click.echo(f"{prefix}🔘 Button: {node.get('text', 'Untitled')}")
        if node.get("resourceId"):
            click.echo(f"{prefix}  └─ ID: {node['resourceId']}")
    elif node_type == "label" and node.get("text"):
        click.echo(f"{prefix}📄 Text: {node['text'][:50]}{'...' if len(node.get('text', '')) > 50 else ''}")
    elif node_type == "input":
        click.echo(f"{prefix}📝 Input: {node.get('resourceId', 'no-id')}")
    
    # Display children
    if node.get("children"):
        for child in node["children"]:
            _display_tree_summary(child, indent + 1)


@cli.command()
def dump_fast():
    """Ultra-fast dump using regex parsing - no XML overhead"""
    try:
        # Dump UI to XML
        xml_path = dump_ui()
        click.echo(f"Dumped UI to: {xml_path}")
        
        # Read as text
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Use ultra-fast regex parser
        elements = parse_ultra_fast(xml_content)
        
        # Save to JSON
        output_file = Path.cwd() / "dumpXMLtoJson.json"
        with open(output_file, 'w') as f:
            json.dump({"elements": elements, "total": len(elements)}, f, indent=2)
        
        click.echo(f"\nUltra-fast dump saved to: {output_file}")
        click.echo(f"Found {len(elements)} actionable elements")
        
        # Show first few
        for elem in elements[:5]:
            text = elem.get('text', '[No text]')[:40]
            action = elem.get('action', '')
            res_id = elem.get('resourceId', '')
            
            if action:
                click.echo(f"[{elem['id']}] {text} → {action.upper()}")
                if res_id:
                    click.echo(f"      ID: {res_id}")
        
        if len(elements) > 5:
            click.echo(f"... and {len(elements) - 5} more")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def dump_minimal():
    """Dumps UI in minimal format - optimized for fast LLM processing"""
    try:
        # Dump UI to XML
        xml_path = dump_ui()
        click.echo(f"Dumped UI to: {xml_path}")
        
        # Parse to minimal JSON
        minimal_data = parse_minimal_for_llm(xml_path)
        
        # Save to JSON file
        output_file = Path.cwd() / "dumpMinimal.json"
        with open(output_file, 'w') as f:
            json.dump(minimal_data, f, indent=2)
        
        # Show stats
        click.echo(f"\n✓ Minimal dump saved to: {output_file}")
        click.echo(f"Elements: {minimal_data['n']}")
        
        # Show detected patterns
        if minimal_data.get('m'):
            click.echo("\nDetected UI patterns:")
            for pattern, indices in minimal_data['m'].items():
                click.echo(f"  - {pattern}: {len(indices)} elements")
        
        # Compare file sizes
        original_size = Path(xml_path).stat().st_size
        minimal_size = Path(output_file).stat().st_size
        reduction = (1 - minimal_size/original_size) * 100
        
        click.echo(f"\nSize reduction: {reduction:.1f}% smaller")
        click.echo(f"  XML: {original_size:,} bytes")
        click.echo(f"  JSON: {minimal_size:,} bytes")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument('goal')
def analyze(goal):
    """Analyze screen and suggest action for a specific goal"""
    try:
        from .planner import analyze_screen_for_goal
        
        # Analyze screen
        result = analyze_screen_for_goal(goal)
        
        # Display analysis
        click.echo(f"\n=== Analysis for goal: '{goal}' ===")
        click.echo(f"Recommended action: {result['action']}")
        click.echo(f"Target element: {result['element']['label']} (index {result['element_index']})")
        click.echo(f"Reason: {result['reason']}")
        click.echo(f"Confidence: {result['confidence']:.0%}")
        
        if result['element']['clickable']:
            click.echo(f"\nElement details:")
            click.echo(f"- Type: {result['element']['type']}")
            click.echo(f"- Location: {result['element']['location']}")
            click.echo(f"- Enabled: {result['element']['enabled']}")
        
    except FileNotFoundError:
        click.echo("Error: No screen dump found. Run 'dump' or 'dump-llm' first.", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument('goal')
def execute(goal):
    """Execute action for a specific goal (analyze + run)"""
    try:
        from .planner import analyze_screen_for_goal
        from .android import tap_node
        
        # Analyze screen
        result = analyze_screen_for_goal(goal)
        
        # Display plan
        click.echo(f"\n=== Executing goal: '{goal}' ===")
        click.echo(f"Action: {result['action']} on {result['element']['label']}")
        click.echo(f"Reason: {result['reason']}")
        click.echo(f"Confidence: {result['confidence']:.0%}")
        
        # Confirm before executing
        if not click.confirm("\nProceed with this action?", default=False):
            click.echo("Aborted.")
            return
        
        # Execute based on action type
        if result['action'] == 'click':
            element = result['element']
            selector = {
                "resource-id": element['identifiers']['resource_id'],
                "text": element['identifiers']['text'],
                "content-desc": element['identifiers']['content_desc']
            }
            tap_node(selector)
            click.echo("✓ Click executed successfully")
        else:
            click.echo(f"Action '{result['action']}' not yet implemented")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def smart_dump():
    """Smart UI dump - organized and easy for LLMs to understand"""
    try:
        # Dump UI to XML
        xml_path = dump_ui()
        click.echo(f"Dumped UI to: {xml_path}")
        
        # Parse with simple parser
        ui_data = parse_ui_tree(xml_path)
        
        # Save to JSON file
        output_file = Path.cwd() / "smartDump.json"
        with open(output_file, 'w') as f:
            json.dump(ui_data, f, indent=2)
        
        # Display summary
        click.echo(f"\n✓ Smart dump saved to: {output_file}")
        
        # Show summary
        summary = ui_data["summary"]
        click.echo(f"\nScreen Summary:")
        click.echo(f"  Total elements: {summary['total_elements']}")
        click.echo(f"  Clickable: {summary['clickable']}")
        click.echo(f"  Input fields: {summary['inputs']}")
        click.echo(f"  Buttons: {summary['buttons']}")
        
        # Show layout
        click.echo(f"\nScreen Layout:")
        for area, elements in ui_data["layout"].items():
            if elements:
                click.echo(f"  {area.upper()}: {len(elements)} elements")
                for elem in elements[:3]:  # Show first 3
                    click.echo(f"    [{elem['id']}] {elem['label']} ({elem['type']})")
        
        # Show detected patterns
        if ui_data["patterns"]:
            click.echo(f"\nDetected Patterns:")
            for pattern, info in ui_data["patterns"].items():
                if info.get("detected"):
                    click.echo(f"  ✓ {pattern}")
                    if pattern == "authentication":
                        for elem in info["elements"]:
                            click.echo(f"    - [{elem['id']}] {elem['label']}")
        
        # Quick reference
        click.echo(f"\nQuick Reference:")
        click.echo(f"  - Use element ID to interact")
        click.echo(f"  - Example: 'click element 0' or 'type in element 2'")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


@cli.command()
def dump_tree():
    """Dumps UI in hierarchical tree format - organized by screen sections"""
    try:
        # Dump UI to XML
        xml_path = dump_ui()
        click.echo(f"Dumped UI to: {xml_path}")
        
        # Parse to hierarchical structure
        tree_data = parse_hierarchical_for_llm(xml_path)
        
        # Save to JSON file
        output_file = Path.cwd() / "dumpTree.json"
        with open(output_file, 'w') as f:
            json.dump(tree_data, f, indent=2)
        
        # Display summary
        click.echo(f"\n✓ Hierarchical dump saved to: {output_file}")
        click.echo(f"\nScreen Structure:")
        
        # Show sections
        for section in tree_data["screen"]["sections"]:
            click.echo(f"  - {section['type'].upper()}: {len(section.get('children', []))} elements")
        
        # Show quick actions
        if tree_data["screen"]["quick_actions"]:
            click.echo(f"\nQuick Actions Found:")
            for action in tree_data["screen"]["quick_actions"]:
                click.echo(f"  [{action['idx']}] {action['label']} ({action['type']})")
        
        # Show forms
        if tree_data["screen"]["forms"]:
            click.echo(f"\nForms Detected:")
            for form in tree_data["screen"]["forms"]:
                click.echo(f"  - {form['type']}: {len(form['fields'])} fields")
        
        # Show suggestions
        if tree_data.get("suggestions"):
            click.echo(f"\nSuggestions:")
            for key, suggestion in tree_data["suggestions"].items():
                click.echo(f"  - {suggestion.get('message', key)}")
        
        click.echo(f"\nTotal actionable elements: {tree_data['count']}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()