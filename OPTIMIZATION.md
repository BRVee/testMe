# JSON Optimization for LLM Processing

## New Minimal Format

The `dump-minimal` command creates a highly optimized JSON that's 70-90% smaller than the original XML.

### Before (Original XML → JSON):

```json
{
  "screen_elements": [
    {
      "index": 0,
      "type": "text",
      "label": "Welcome",
      "clickable": false,
      "enabled": true,
      "location": { "x": 250, "y": 100 },
      "size": { "width": 500, "height": 50 },
      "identifiers": {
        "resource_id": "com.app:id/welcome_text",
        "text": "Welcome",
        "content_desc": ""
      },
      "properties": {
        "focusable": false,
        "scrollable": false,
        "long_clickable": false,
        "password": false,
        "selected": false
      },
      "ui_class": "android.widget.TextView"
    }
    // ... many more elements
  ],
  "total_elements": 47,
  "clickable_elements": 12
}
```

### After (Minimal Format):

```json
{
  "e": [
    { "i": 0, "t": "I", "l": "Username", "h": "type" },
    { "i": 1, "t": "I", "l": "Password", "h": "type" },
    { "i": 2, "t": "B", "l": "Login", "c": 1, "h": "click" },
    { "i": 3, "t": "T", "l": "Forgot password?", "c": 1, "h": "click" }
  ],
  "n": 4,
  "m": {
    "auth": [0, 1, 2],
    "action": [2]
  }
}
```

## Key Optimizations:

1. **Filtered Elements**:

   - ❌ Disabled/invisible elements
   - ❌ Non-interactive containers
   - ❌ Duplicate elements
   - ❌ Tiny decorative elements (<20px)
   - ✅ Only actionable UI elements

2. **Minimal Keys**:

   - `i` = index (instead of "index")
   - `t` = type (B=Button, T=Text, I=Input, L=List)
   - `l` = label
   - `c` = clickable (only if true)
   - `h` = hint (click/type/select)

3. **Smart Grouping**:

   - Similar list items are grouped
   - Pattern detection for common UI elements
   - Quick lookup map for auth/nav/action patterns

4. **Size Reduction**:
   - 70-90% smaller than XML
   - 50-80% smaller than full JSON
   - Faster LLM processing
   - Lower API costs

## Usage:

```bash
# Standard dump (full details)
python -m src dump-llm

# Minimal dump (optimized for LLM)
python -m src dump-minimal

# Compare sizes
ls -lh window_dump.xml dumpMinimal.json
```

## LLM Benefits:

1. **Faster Processing**: Less tokens = faster responses
2. **Better Focus**: Only relevant elements shown
3. **Pattern Recognition**: Pre-grouped UI patterns
4. **Lower Costs**: Fewer tokens = cheaper API calls
