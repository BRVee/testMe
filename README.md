# QE-First: Zero-Instrumentation Android UI Driver

A stateless Android UI automation tool that uses accessibility services to interact with release builds.

## Features
- Dumps live accessibility tree as XML
- Converts XML to clean JSON format
- Uses LLM to select nodes for interaction
- Replays clicks by node identity (not coordinates)

## Usage
```bash
python -m qe dump  # dumps XML → window_dump.xml + prints JSON
python -m qe plan  # reads JSON, asks LLM, prints chosen node
python -m qe run   # performs the click (prompts Y/N first)
```

## Requirements
- Python 3.11+
- Android device with USB debugging enabled
- adb installed and in PATH