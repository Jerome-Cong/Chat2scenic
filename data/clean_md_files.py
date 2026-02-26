#!/usr/bin/env python3
"""
Script to clean markdown files (converted from PDF) for RAG system usage.
Removes PDF artifacts, fixes whitespace issues, and structures content better.
Processes all markdown files in the data/md directory.
"""

import re
from pathlib import Path
from typing import Dict, Tuple

# Document metadata for headers
DOCUMENT_INFO = {
    "R171": {
        "title": "UN Regulation No. 171 - Driver Control Assistance Systems (DCAS)",
        "doc_id": "E/ECE/TRANS/505/Rev.3/Add.170",
        "subject": "Uniform Provisions Concerning the Approval of Vehicles with regard to Driver Control Assistance Systems",
        "page_header": r'E/ECE/TRANS/505/Rev\.3/Add\.170',
    },
    "R157": {
        "title": "UN Regulation No. 157 - Automated Lane Keeping Systems (ALKS)",
        "doc_id": "E/ECE/TRANS/505/Rev.3/Add.156",
        "subject": "Uniform Provisions Concerning the Approval of Vehicles with regard to Automated Lane Keeping Systems",
        "page_header": r'E/ECE/TRANS/505/Rev\.3/Add\.156',
    },
    "R152": {
        "title": "UN Regulation No. 152 - Advanced Emergency Braking System (AEBS)",
        "doc_id": "E/ECE/TRANS/505/Rev.3/Add.151/Rev.2",
        "subject": "Uniform Provisions Concerning the Approval of Motor Vehicles with regard to the Advanced Emergency Braking System (AEBS) for M1 and N1 vehicles",
        "page_header": r'E/ECE/TRANS/505/Rev\.3/Add\.151',
    },
    "NHTSA": {
        "title": "NHTSA Pre-Crash Scenario Typology for Crash Avoidance Research",
        "doc_id": "DOT HS 810 767",
        "subject": "Pre-Crash Scenarios depicting vehicle movements and dynamics prior to crashes",
        "page_header": None,  # NHTSA doc doesn't have repeated headers
    },
}


def detect_document_type(filename: str, content: str) -> str:
    """Detect document type from filename or content."""
    filename_upper = filename.upper()
    
    if "R171" in filename_upper:
        return "R171"
    elif "R157" in filename_upper:
        return "R157"
    elif "R152" in filename_upper:
        return "R152"
    elif "NHTSA" in filename_upper or "DOT HS" in content[:500]:
        return "NHTSA"
    
    # Default based on content
    if "E/ECE/TRANS/505" in content[:1000]:
        if "Add.170" in content[:1000]:
            return "R171"
        elif "Add.156" in content[:1000]:
            return "R157"
        elif "Add.151" in content[:1000]:
            return "R152"
    
    return "UNKNOWN"


def generate_header(doc_type: str) -> str:
    """Generate a clean header for the document."""
    if doc_type not in DOCUMENT_INFO:
        return ""
    
    info = DOCUMENT_INFO[doc_type]
    header = f"""# {info['title']}

## Document Information
- **Document ID**: {info['doc_id']}
- **Subject**: {info['subject']}

---

"""
    return header


def clean_un_regulation(content: str, doc_type: str) -> str:
    """Clean UN Regulation documents (R152, R157, R171)."""
    info = DOCUMENT_INFO.get(doc_type, {})
    page_header = info.get('page_header')
    
    lines = content.split('\n')
    cleaned_lines = []
    
    # Patterns to remove
    page_header_pattern = re.compile(rf'^{page_header}\s*$') if page_header else None
    standalone_number_pattern = re.compile(r'^\d{1,3}\s*$')
    dots_pattern = re.compile(r'\.{5,}')  # 5+ dots
    ge_reference_pattern = re.compile(r'^GE\.\d{2}-\d+\s*\(E\)\s*$')
    page_pattern = re.compile(r'^Page\s*$', re.IGNORECASE)
    
    # Patterns for joining broken lines
    paragraph_number_pattern = re.compile(r'^(\d+\.(?:\d+\.)*)\s*$')
    list_item_alone_pattern = re.compile(r'^\s*\([a-z]\)\s*$')
    list_item_roman_alone = re.compile(r'^\s*\([ivx]+\)\s*$')
    
    skip_next_empty = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Skip page headers
        if page_header_pattern and page_header_pattern.match(line.strip()):
            skip_next_empty = True
            i += 1
            continue
        
        # Skip standalone page numbers
        if standalone_number_pattern.match(line.strip()):
            i += 1
            continue
        
        # Skip GE reference lines
        if ge_reference_pattern.match(line.strip()):
            i += 1
            continue
        
        # Skip "Page" alone
        if page_pattern.match(line.strip()):
            i += 1
            continue
        
        # Skip lines that are mostly dots (TOC entries)
        if dots_pattern.search(line):
            i += 1
            continue
        
        # Skip empty lines after page headers
        if skip_next_empty and line.strip() == '':
            skip_next_empty = False
            i += 1
            continue
        skip_next_empty = False
        
        # Clean excessive internal whitespace
        if line.strip():
            leading_ws = len(line) - len(line.lstrip())
            leading = line[:leading_ws]
            rest = line[leading_ws:]
            rest = re.sub(r'  +', ' ', rest)
            line = leading + rest
        
        # Join paragraph numbers with following content
        para_match = paragraph_number_pattern.match(line.strip())
        if para_match and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not paragraph_number_pattern.match(next_line):
                line = line.strip() + ' ' + next_line
                i += 1
        
        # Join list items with following content
        if list_item_alone_pattern.match(line.strip()) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line:
                line = line.strip() + ' ' + next_line
                i += 1
        
        # Join roman numeral list items
        if list_item_roman_alone.match(line.strip()) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line:
                line = line.strip() + ' ' + next_line
                i += 1
        
        cleaned_lines.append(line)
        i += 1
    
    content = '\n'.join(cleaned_lines)
    
    # Clean up multiple consecutive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Join lines that were split mid-sentence
    content = re.sub(r'([a-z,])\n([a-z])', r'\1 \2', content)
    
    # Remove trailing whitespace
    lines = content.split('\n')
    lines = [line.rstrip() for line in lines]
    content = '\n'.join(lines)
    
    # Find where actual content starts
    intro_match = re.search(r'^(Introduction|1\.\s+Scope)', content, re.MULTILINE)
    if intro_match:
        header = generate_header(doc_type)
        content = header + content[intro_match.start():]
    
    # Final cleanup
    content = content.replace('_________', '---')
    
    # Fix remaining split section numbers
    content = re.sub(r'\n(\d+\.\d+\.)\s*\n([A-Za-z])', r'\n\1 \2', content)
    content = re.sub(r'\n(\d+\.\d+\.\d+\.)\s*\n([A-Za-z])', r'\n\1 \2', content)
    
    # Join standalone list markers
    content = re.sub(r'\n\(([a-z])\)\s*\n\n([A-Z])', r'\n(\1) \2', content)
    content = re.sub(r'\n\(([a-z])\)\s*\n([A-Z])', r'\n(\1) \2', content)
    content = re.sub(r'\n\(([ivx]+)\)\s*\n\n([A-Z])', r'\n(\1) \2', content)
    content = re.sub(r'\n\(([ivx]+)\)\s*\n([A-Z])', r'\n(\1) \2', content)
    
    return content


def clean_nhtsa_document(content: str) -> str:
    """Clean NHTSA document specifically."""
    lines = content.split('\n')
    cleaned_lines = []
    
    # Patterns to skip
    form_patterns = [
        re.compile(r'^Form Approved'),
        re.compile(r'^OMB No\.'),
        re.compile(r'^Public reporting burden'),
        re.compile(r'^NSN \d+'),
        re.compile(r'^Standard Form'),
        re.compile(r'^\d+-\d+$'),
        re.compile(r'^298-102'),
    ]
    
    # Skip the form/documentation page content
    skip_until_preface = True
    
    for i, line in enumerate(lines):
        # Skip until we reach PREFACE
        if skip_until_preface:
            if 'PREFACE' in line:
                skip_until_preface = False
                cleaned_lines.append(line)
            continue
        
        # Skip form-related lines
        skip = False
        for pattern in form_patterns:
            if pattern.match(line.strip()):
                skip = True
                break
        if skip:
            continue
        
        # Skip standalone page numbers
        if re.match(r'^\d{1,3}\s*$', line.strip()):
            continue
        
        # Skip empty table cells
        if re.match(r'^(\|\s*)+$', line.strip()):
            continue
        
        # Clean excessive whitespace
        if line.strip():
            leading_ws = len(line) - len(line.lstrip())
            leading = line[:leading_ws]
            rest = line[leading_ws:]
            rest = re.sub(r'  +', ' ', rest)
            line = leading + rest
        
        cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # Clean up multiple consecutive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Join lines split mid-sentence
    content = re.sub(r'([a-z,])\n([a-z])', r'\1 \2', content)
    
    # Remove trailing whitespace
    lines = content.split('\n')
    lines = [line.rstrip() for line in lines]
    content = '\n'.join(lines)
    
    # Add header
    header = generate_header("NHTSA")
    content = header + content
    
    # Clean up malformed table artifacts
    content = re.sub(r'\|\s*---\s*\|', '', content)
    content = re.sub(r'\n\|\s*\|\s*\|\s*\|', '', content)
    
    return content


def clean_markdown_file(input_file: Path, output_dir: Path) -> Tuple[str, int, int]:
    """
    Clean a markdown file and save to output directory.
    Returns: (output_filename, original_lines, cleaned_lines)
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_lines = len(content.split('\n'))
    
    # Detect document type
    doc_type = detect_document_type(input_file.name, content)
    print(f"  Detected type: {doc_type}")
    
    # Apply appropriate cleaning
    if doc_type == "NHTSA":
        cleaned_content = clean_nhtsa_document(content)
    elif doc_type in ["R152", "R157", "R171"]:
        cleaned_content = clean_un_regulation(content, doc_type)
    else:
        # Generic cleaning for unknown types
        cleaned_content = clean_un_regulation(content, doc_type)
    
    cleaned_lines = len(cleaned_content.split('\n'))
    
    # Save to output directory
    output_file = output_dir / input_file.name
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)
    
    return output_file.name, original_lines, cleaned_lines


def main():
    """Main entry point."""
    # Paths
    input_dir = Path("/home/dellpro2/wenting/scenario-generation-chatbot/data/md")
    output_dir = Path("/home/dellpro2/wenting/scenario-generation-chatbot/data/cleaned")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all markdown files (exclude backup files)
    md_files = [f for f in input_dir.glob("*.md") if "_original" not in f.name.lower()]
    
    print("=" * 60)
    print("Markdown File Cleaner for RAG System")
    print("=" * 60)
    print(f"\nInput directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Found {len(md_files)} file(s) to process\n")
    
    results = []
    
    for md_file in md_files:
        print(f"Processing: {md_file.name}")
        try:
            output_name, orig, cleaned = clean_markdown_file(md_file, output_dir)
            reduction = (1 - cleaned / orig) * 100 if orig > 0 else 0
            results.append((output_name, orig, cleaned, reduction))
            print(f"  Original: {orig} lines -> Cleaned: {cleaned} lines ({reduction:.1f}% reduction)")
        except Exception as e:
            print(f"  ERROR: {str(e)}")
            results.append((md_file.name, 0, 0, 0))
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"{'File':<30} {'Original':>10} {'Cleaned':>10} {'Reduction':>10}")
    print("-" * 60)
    
    total_orig = 0
    total_cleaned = 0
    
    for name, orig, cleaned, reduction in results:
        print(f"{name:<30} {orig:>10} {cleaned:>10} {reduction:>9.1f}%")
        total_orig += orig
        total_cleaned += cleaned
    
    print("-" * 60)
    total_reduction = (1 - total_cleaned / total_orig) * 100 if total_orig > 0 else 0
    print(f"{'TOTAL':<30} {total_orig:>10} {total_cleaned:>10} {total_reduction:>9.1f}%")
    print("=" * 60)
    print(f"\nCleaned files saved to: {output_dir}")


if __name__ == "__main__":
    main()
