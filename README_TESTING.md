# Testing Instructions

To test the QE-First Android UI driver:

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Connect an Android device with USB debugging enabled
   ```bash
   adb devices  # Should show your device
   ```

## Run Tests
1. Unit tests:
   ```bash
   python3 -m pytest tests/ -v
   ```

2. CLI commands:
   ```bash
   # Dump UI and see JSON output
   python3 -m qe dump
   
   # Plan which node to click (uses stub LLM)
   python3 -m qe plan
   
   # Execute the click (will prompt for confirmation)
   python3 -m qe run
   ```

## Expected Behavior
- `dump`: Creates window_dump.xml and prints JSON list of UI nodes
- `plan`: Reads the dump and selects first clickable node with text
- `run`: Shows selected node and prompts before clicking

## Note
The current implementation uses a stub for the LLM that simply picks the first clickable node with text. Future versions will integrate with actual LLM APIs.