import click
import json
from pathlib import Path

from .android import dump_ui, tap_node
from .parser import parse
from .planner import choose_node


@click.group()
def cli():
    """QE-First: Zero-instrumentation Android UI driver"""
    pass


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


if __name__ == "__main__":
    cli()