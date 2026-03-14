import json
from scenic.syntax.parser import parse_string


def parse_scenic(scenic_code: str):
    return parse_string(scenic_code, 'exec')


def parse_json_from_text(text: str) -> dict:
    text = text.strip()
    
    # Try to parse as direct JSON
    if text.startswith('{'):
        try:
            json_data = json.loads(text)
            return json_data
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Failed to parse as direct JSON: {e}")
    
    # Try to extract JSON from markdown code block
    if '```json' in text or '```' in text:
        try:
            start_marker = '```json'
            if start_marker in text:
                start = text.find(start_marker) + len(start_marker)
            else:
                start = text.find('```') + 3
            
            end = text.find('```', start)
            if end == -1:
                end = len(text)
            
            json_str = text[start:end].strip()
            json_data = json.loads(json_str)
            return json_data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[DEBUG] Failed to extract JSON from code block: {e}")
    
  
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            json_str = text[start:end]
            json_data = json.loads(json_str)
            return json_data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[DEBUG] Failed to extract JSON from text: {e}")
    

    return {}
