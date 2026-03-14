
import os
import json
import sys
import re
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from core.agents.base import BaseAgent
from core.config import get_settings

# Load settings
settings = get_settings()


def remove_comments_from_scenic(scenic_code: str) -> str:
    lines = scenic_code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        if re.match(r'^\s*#+\s*$', line):
            continue
        
        if re.match(r'^\s*#.*#\s*$', line) and line.count('#') >= 2:
            stripped = line.strip()
            if stripped.startswith('#') and stripped.endswith('#'):
                continue
        
        if '#' in line:
            if line.strip().startswith('#'):
                continue
            
            in_string = False
            quote_char = None
            cleaned_line = []
            
            for i, char in enumerate(line):
                if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False
                        quote_char = None
                
                if char == '#' and not in_string:
                    # This is a comment, stop here
                    break
                
                cleaned_line.append(char)
            
            line = ''.join(cleaned_line).rstrip()
        
        if line.strip():
            cleaned_lines.append(line)
    
    result = '\n'.join(cleaned_lines)
    
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
    
    return result.strip()


class ScenicToLogicalAgent(BaseAgent):
    
    def __init__(self):
        with open("core/prompts/code2logical.txt", 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        super().__init__(
            prompt_template=prompt_template,
            model_name="gemini-2.5-flash",
            model_provider="google_genai",
            use_rag=False
        )
    
    def process(self, scenic_content: str) -> str:
        response = self.invoke(context={"scenic_code": scenic_content})
        return response.strip()


def parse_logical_structure(llm_response: str, scenic_code: str) -> Dict[str, Any]:
    cleaned_code = remove_comments_from_scenic(scenic_code)
    
    result = {
        "Scenario": {
            "description": "",
            "code": cleaned_code
        },
        "Egos": [],
        "Adversarials": [],
        "Spatial Relation": {
            "description": "",
            "code": ""
        },
        "Requirement and restrictions": {
            "description": "",
            "code": ""
        }
    }
    
    try:
        cleaned_response = llm_response.strip()
        if cleaned_response.startswith("```"):
            lines = cleaned_response.split('\n')
            cleaned_response = '\n'.join(lines[1:-1]) if len(lines) > 2 else cleaned_response
        
        llm_data = json.loads(cleaned_response)
        
        if "Scenario" in llm_data:
            result["Scenario"]["description"] = llm_data["Scenario"]
        if "Ego" in llm_data:
            if isinstance(llm_data["Ego"], list):
                result["Egos"] = [{"description": ego, "code": ""} for ego in llm_data["Ego"]]
            else:
                result["Egos"] = [{"description": llm_data["Ego"], "code": ""}]
        if "Egos" in llm_data and isinstance(llm_data["Egos"], list):
            result["Egos"] = [{"description": ego, "code": ""} for ego in llm_data["Egos"]]
        if "Adversarials" in llm_data and isinstance(llm_data["Adversarials"], list):
            result["Adversarials"] = [{"description": adv, "code": ""} for adv in llm_data["Adversarials"]]
        if "Spatial Relation" in llm_data:
            result["Spatial Relation"]["description"] = llm_data["Spatial Relation"]
        if "Requirement and restrictions" in llm_data:
            result["Requirement and restrictions"]["description"] = llm_data["Requirement and restrictions"]
            
    except json.JSONDecodeError:
        pass
    
    code_lines = scenic_code.split('\n')
    
    ego_section = extract_section_code(code_lines, "Ego")
    
    if ego_section:
        ego_objects_raw = extract_individual_objects_from_section(ego_section)
        
        ego_objects = []
        for obj in ego_objects_raw:
            if re.match(r'ego\s*=\s*new\s+', obj.strip(), re.IGNORECASE):
                ego_objects.append(ego_section)
                break
        
        if not ego_objects:
            ego_objects = [ego_section]
    else:
        ego_behavior_code = extract_section_code(code_lines, "Ego Behavior")
        ego_object_code = extract_section_code(code_lines, "Ego object")
        
        if ego_behavior_code or ego_object_code:
            combined_ego = (ego_behavior_code + "\n\n" + ego_object_code).strip()
            ego_objects = [combined_ego] if combined_ego else []
        else:
            ego_objects = []
    
    if len(result["Egos"]) > 0:
        for i, ego in enumerate(result["Egos"]):
            if i < len(ego_objects):
                ego["code"] = ego_objects[i]
            else:
                if ego_objects:
                    ego["code"] = ego_objects[0] if len(ego_objects) == 1 else ""
    else:
        for ego_code in ego_objects:
            if ego_code.strip():
                result["Egos"].append({
                    "description": "",
                    "code": ego_code
                })
    
    adv_sections = extract_all_sections(code_lines, "Adversarial")
    
    adversary_objects = []
    
    if adv_sections:
        for section in adv_sections:
            objects = extract_individual_objects_from_section(
                section,
                r'\w+\s*=\s*new\s+' 
            )
            
            if objects:
                behavior_match = re.search(r'(behavior\s+\w+\s*\([^)]*\):.*?)(?=\n\w+\s*=\s*new\s+|\Z)', section, re.DOTALL)
                params_and_consts = []
                
                for line in section.split('\n'):
                    stripped = line.strip()
                    if stripped.startswith('param '):
                        params_and_consts.append(line)
                    elif stripped and not stripped.startswith('#') and not stripped.startswith('behavior') and '=' in stripped and 'new ' not in stripped:
                        if re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
                            params_and_consts.append(line)
                
                params_code = '\n'.join(params_and_consts) if params_and_consts else ""
                behavior_code = behavior_match.group(1).strip() if behavior_match else ""
                
                for obj in objects:
                    combined_parts = []
                    if params_code:
                        combined_parts.append(params_code)
                    if behavior_code:
                        combined_parts.append(behavior_code)
                    combined_parts.append(obj)
                    adversary_objects.append('\n\n'.join(combined_parts))
            else:
                if re.search(r'behavior\s+\w+\s*\(', section):
                    adversary_objects.append(section)
    
    if not adversary_objects:
        adv_behavior_code = extract_section_code(code_lines, "Adversarial Behavior")
        adv_object_code = extract_section_code(code_lines, "Adversarial object")
        
        if adv_behavior_code and adv_object_code:
            objects = extract_individual_objects_from_section(adv_object_code)
            for obj in objects:
                adversary_objects.append(adv_behavior_code + "\n\n" + obj)
        elif adv_behavior_code or adv_object_code:
            adversary_objects = extract_adversary_objects(scenic_code)
    
    if len(result["Adversarials"]) > 0:
        for i, adv in enumerate(result["Adversarials"]):
            if i < len(adversary_objects):
                adv["code"] = adversary_objects[i]
            else:
                if adversary_objects:
                    adv["code"] = adversary_objects[0] if len(adversary_objects) == 1 else ""
    else:
        for adv_code in adversary_objects:
            if adv_code.strip():
                result["Adversarials"].append({
                    "description": "",
                    "code": adv_code
                })
    
    spatial_code = extract_section_code(code_lines, "Spatial Relation")
    result["Spatial Relation"]["code"] = spatial_code
    
    req_code = extract_section_code(code_lines, "Requirements and Restrictions")
    result["Requirement and restrictions"]["code"] = req_code
    
    return result


def extract_individual_objects_from_section(section_code: str, object_pattern: str = None) -> list:
    if object_pattern is None:
        object_pattern = r'\w+\s*=\s*new\s+'
    
    pattern = re.compile(object_pattern, re.IGNORECASE)
    
    object_definitions = []
    current_def = []
    in_definition = False
    
    for line in section_code.split('\n'):
        if pattern.search(line):
            if current_def:
                object_definitions.append('\n'.join(current_def).strip())
            current_def = [line]
            in_definition = True
        elif in_definition:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                current_def.append(line)
                if not line.rstrip().endswith(',') and not line.rstrip().endswith('\\'):
                    object_definitions.append('\n'.join(current_def).strip())
                    current_def = []
                    in_definition = False
            elif stripped.startswith('#'):
                if current_def:
                    object_definitions.append('\n'.join(current_def).strip())
                    current_def = []
                    in_definition = False
    
    if current_def:
        object_definitions.append('\n'.join(current_def).strip())
    
    return object_definitions


def extract_adversary_objects(scenic_code: str) -> list:
    code_lines = scenic_code.split('\n')
    
    adv_section = extract_section_code(code_lines, "Adversarial")
    if not adv_section:
        adv_behavior_code = extract_section_code(code_lines, "Adversarial Behavior")
        adv_object_section = extract_section_code(code_lines, "Adversarial object")
        if not adv_object_section:
            return []
    else:
        adv_behavior_code = adv_section
        adv_object_section = adv_section
    
    adversary_pattern = re.compile(
        r'(adv[_\d]*|adversary[_\d]*|lead[_\d]*|ped[_\d]*|debris[_\d]*|trash[_\d]*|pedestrian[_\d]*|bicycle[_\d]*|truck[_\d]*)\s*=\s*new\s+',
        re.IGNORECASE
    )
    
    adversary_definitions = []
    current_def = []
    in_definition = False
    
    for line in adv_object_section.split('\n'):
        if adversary_pattern.search(line):
            if current_def:
                adversary_definitions.append('\n'.join(current_def).strip())
            current_def = [line]
            in_definition = True
        elif in_definition:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                current_def.append(line)
                if not line.rstrip().endswith(',') and not line.rstrip().endswith('\\'):
                    adversary_definitions.append('\n'.join(current_def).strip())
                    current_def = []
                    in_definition = False
    
    if current_def:
        adversary_definitions.append('\n'.join(current_def).strip())
    
    param_pattern = re.compile(r'param\s+\w+', re.IGNORECASE)
    const_pattern = re.compile(r'^[A-Z_][A-Z0-9_]*\s*=', re.MULTILINE)
    
    params_for_adv = []
    constants_for_adv = []
    
    behavior_section_lines = adv_behavior_code.split('\n') if adv_behavior_code else []
    for line in behavior_section_lines:
        stripped = line.strip()
        if stripped.startswith('param '):
            params_for_adv.append(line.strip())
        elif stripped and not stripped.startswith('#') and not stripped.startswith('behavior'):
            if re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
                constants_for_adv.append(line.strip())
    
    for line in adv_object_section.split('\n'):
        stripped = line.strip()
        if stripped.startswith('param '):
            params_for_adv.append(line.strip())
        elif stripped and not stripped.startswith('#') and '=' in stripped and 'new ' not in stripped:
            if re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
                constants_for_adv.append(line.strip())
    
    all_params = list(set(params_for_adv + constants_for_adv))
    params_code = '\n'.join(all_params)
    
    complete_adversaries = []
    for adv_def in adversary_definitions:
        complete_code = params_code + "\n\n" + adv_behavior_code + "\n\n" + adv_def if adv_behavior_code else params_code + "\n\n" + adv_def
        complete_adversaries.append(complete_code.strip())
    
    return complete_adversaries


def extract_section_code(code_lines: list, section_header: str) -> str:
    in_section = False
    section_code = []
    found_section = False
    skip_header_box = False
    
    for i, line in enumerate(code_lines):
        # Only match section headers in comment lines
        stripped = line.strip()
        if section_header in line and not in_section and stripped.startswith("#"):
            in_section = True
            found_section = True
            skip_header_box = True
            continue
        
        if in_section:
            if skip_header_box and line.strip().startswith("#####") and line.strip().endswith("#####"):
                skip_header_box = False
                continue
                
            stripped = line.strip()
            if stripped.startswith("#") and not stripped == "#" and len(stripped) > 10:
                inner_text = stripped.replace("#", "").strip()
                if inner_text:
                    break
            
            if not section_code and not line.strip():
                continue
                
            section_code.append(line)
    
    if not found_section:
        return ""
    
    while section_code:
        last_line = section_code[-1].strip()
        if not last_line or (last_line.startswith("#####") and last_line.endswith("#####")):
            section_code.pop()
        else:
            break
    
    code = '\n'.join(section_code).strip()
    return code


def extract_all_sections(code_lines: list, section_header: str) -> list:
    sections = []
    current_section = []
    in_section = False
    skip_header_box = False
    
    for i, line in enumerate(code_lines):
        stripped = line.strip()
        
        is_section_header = False
        if stripped.startswith("#") and section_header in line:
            comment_text = stripped.replace("#", "").strip()
            if comment_text.startswith(section_header):
                is_section_header = True
        
        if is_section_header:
            if in_section and current_section:
                while current_section:
                    last_line = current_section[-1].strip()
                    if not last_line or (last_line.startswith("#####") and last_line.endswith("#####")):
                        current_section.pop()
                    else:
                        break
                if current_section:
                    sections.append('\n'.join(current_section).strip())
                current_section = []
            in_section = True
            skip_header_box = True
            continue
        
        if in_section:
            if skip_header_box and stripped.startswith("#####") and stripped.endswith("#####"):
                skip_header_box = False
                continue
            
            if stripped.startswith("#") and not stripped == "#" and len(stripped) > 10:
                comment_text = stripped.replace("#", "").strip()
                major_sections = ["Description", "Header", "Ego", "Adversarial", "Spatial Relation", 
                                "Requirements and Restrictions", "Requirement and restrictions"]
                is_different_section = False
                for major_section in major_sections:
                    if comment_text.startswith(major_section) and not comment_text.startswith(section_header):
                        is_different_section = True
                        break
                
                if is_different_section:
                    if current_section:
                        while current_section:
                            last_line = current_section[-1].strip()
                            if not last_line or (last_line.startswith("#####") and last_line.endswith("#####")):
                                current_section.pop()
                            else:
                                break
                        if current_section:
                            sections.append('\n'.join(current_section).strip())
                    in_section = False
                    current_section = []
                    continue
            
            if not current_section and not stripped:
                continue
                
            current_section.append(line)
    
    if in_section and current_section:
        while current_section:
            last_line = current_section[-1].strip()
            if not last_line or (last_line.startswith("#####") and last_line.endswith("#####")):
                current_section.pop()
            else:
                break
        if current_section:
            sections.append('\n'.join(current_section).strip())
    
    return sections


def process_scenic_file(agent: ScenicToLogicalAgent, input_path: str, output_dir: str = "results/logical_structures"):
    print(f"Processing: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        scenic_content = f.read()
    
    llm_response = agent.process(scenic_content)
    
    structured_data = parse_logical_structure(llm_response, scenic_content)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    input_file = Path(input_path)
    output_filename = input_file.stem + ".json"
    output_file = output_path / output_filename
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, indent=2, ensure_ascii=False)
    
    return output_file


def process_directory(agent: ScenicToLogicalAgent, directory_path: str, output_dir: str = "data/json"):
    path = Path(directory_path)
    scenic_files = sorted(path.glob("*.scenic"))
    
    if not scenic_files:
        return
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = 0
    
    for i, file_path in enumerate(scenic_files, 1):
        try:
            process_scenic_file(agent, str(file_path), output_dir=str(output_path))
            successful += 1
        except Exception as e:
            failed += 1
            continue


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract logical structure from Scenic files and save as JSON"
    )
    parser.add_argument(
        "path", 
        help="Path to a Scenic file or directory"
    )
    parser.add_argument(
        "-o", "--output-dir", 
        default="data/json",
        help="Output directory for JSON files (default: results/logical_structures)"
    )
    
    args = parser.parse_args()
    
    # Check path exists
    path = Path(args.path)
    if not path.exists():
        sys.exit(1)
    
    try:
        agent = ScenicToLogicalAgent()
    except Exception as e:
        sys.exit(1)
    
    # Process file or directory
    if path.is_file():
        process_scenic_file(agent, str(path), output_dir=args.output_dir)
    elif path.is_dir():
        process_directory(agent, str(path), output_dir=args.output_dir)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

