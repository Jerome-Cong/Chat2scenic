#!/usr/bin/env python3
"""
Script to clean R171e.md for RAG system usage.
Removes PDF artifacts, fixes whitespace issues, and structures content better.
"""

import re
from pathlib import Path

def clean_r171e_for_rag(input_file: str, output_file: str):
    """Clean the R171e markdown file for RAG system."""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into lines for processing
    lines = content.split('\n')
    cleaned_lines = []
    
    # Patterns to remove
    page_header_pattern = re.compile(r'^E/ECE/TRANS/505/Rev\.3/Add\.170\s*$')
    standalone_number_pattern = re.compile(r'^\d{1,3}\s*$')
    dots_pattern = re.compile(r'\.{5,}')  # 5+ dots
    ge_reference_pattern = re.compile(r'^GE\.\d{2}-\d+\s*\(E\)\s*$')
    
    # Patterns for joining broken lines
    paragraph_number_pattern = re.compile(r'^(\d+\.(?:\d+\.)*)\s*$')  # "1." or "1.2." alone on a line
    list_item_alone_pattern = re.compile(r'^\s*\([a-z]\)\s*$')  # "(a)" alone on a line
    list_item_roman_alone = re.compile(r'^\s*\([ivx]+\)\s*$')  # "(i)", "(ii)" alone
    
    skip_next_empty = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Skip page headers
        if page_header_pattern.match(line.strip()):
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
        
        # Clean excessive internal whitespace (PDF artifact) - but preserve indentation
        if line.strip():
            # Preserve leading whitespace
            leading_ws = len(line) - len(line.lstrip())
            leading = line[:leading_ws]
            rest = line[leading_ws:]
            # Replace multiple spaces with single space in content
            rest = re.sub(r'  +', ' ', rest)
            line = leading + rest
        
        # Join paragraph numbers with following content
        para_match = paragraph_number_pattern.match(line.strip())
        if para_match and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not paragraph_number_pattern.match(next_line):
                # Join with next line
                line = line.strip() + ' ' + next_line
                i += 1  # Skip next line as we've incorporated it
        
        # Join list items (a), (b), etc. with following content
        if list_item_alone_pattern.match(line.strip()) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line:
                line = line.strip() + ' ' + next_line
                i += 1
        
        # Join roman numeral list items (i), (ii), etc. with following content
        if list_item_roman_alone.match(line.strip()) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line:
                line = line.strip() + ' ' + next_line
                i += 1
        
        cleaned_lines.append(line)
        i += 1
    
    # Join the lines
    content = '\n'.join(cleaned_lines)
    
    # Clean up multiple consecutive blank lines (keep max 2)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Join lines that were split mid-sentence (line ending with lowercase letter or comma followed by line starting with lowercase)
    content = re.sub(r'([a-z,])\n([a-z])', r'\1 \2', content)
    
    # Remove trailing whitespace from lines
    lines = content.split('\n')
    lines = [line.rstrip() for line in lines]
    content = '\n'.join(lines)
    
    # Add proper document header for RAG
    header = """# UN Regulation No. 171 - Driver Control Assistance Systems (DCAS)

## Document Information
- **Document ID**: E/ECE/TRANS/505/Rev.3/Add.170
- **Date**: 13 December 2024
- **Subject**: Uniform Provisions Concerning the Approval of Vehicles with regard to Driver Control Assistance Systems
- **Entry into Force**: 22 September 2024

---

"""
    
    # Find where the actual content starts (after the initial metadata)
    # Look for "Introduction" or "1." pattern
    intro_match = re.search(r'^Introduction\s*$', content, re.MULTILINE)
    if intro_match:
        # Remove everything before Introduction and add our clean header
        content = header + content[intro_match.start():]
    
    # Final cleanup - remove any remaining artifacts
    content = content.replace('_________', '---')
    
    # Remove standalone section numbers that are just numbers with dots (like "2.17." on its own)
    content = re.sub(r'\n\d+\.\d+(?:\.\d+)*\s*\n\n', '\n\n', content)
    
    # Clean up footnote references that span lines
    content = re.sub(r'\n(\d+)\s+The levels', r'\n\n[Footnote \1] The levels', content)
    
    # Join standalone list markers with next line content
    content = re.sub(r'\n\(([a-z])\)\s*\n\n([A-Z])', r'\n(\1) \2', content)
    content = re.sub(r'\n\(([a-z])\)\s*\n([A-Z])', r'\n(\1) \2', content)
    content = re.sub(r'\n\(([ivx]+)\)\s*\n\n([A-Z])', r'\n(\1) \2', content)
    content = re.sub(r'\n\(([ivx]+)\)\s*\n([A-Z])', r'\n(\1) \2', content)
    
    # Fix remaining split section numbers (e.g., "5.1." alone followed by content)
    content = re.sub(r'\n(\d+\.\d+\.)\s*\n([A-Za-z])', r'\n\1 \2', content)
    content = re.sub(r'\n(\d+\.\d+\.\d+\.)\s*\n([A-Za-z])', r'\n\1 \2', content)
    
    # Remove excessive spaces within lines
    lines = content.split('\n')
    cleaned_lines2 = []
    for line in lines:
        # Replace multiple spaces with single (but preserve leading whitespace)
        if line.strip():
            leading_ws = len(line) - len(line.lstrip())
            leading = line[:leading_ws]
            rest = line[leading_ws:]
            rest = re.sub(r'  +', ' ', rest)
            line = leading + rest
        cleaned_lines2.append(line)
    content = '\n'.join(cleaned_lines2)
    
    # Write the cleaned content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Cleaned file saved to: {output_file}")
    
    # Print some stats
    original_lines = len(open(input_file, 'r').readlines())
    cleaned_lines_count = len(content.split('\n'))
    print(f"Original lines: {original_lines}")
    print(f"Cleaned lines: {cleaned_lines_count}")
    print(f"Reduction: {(1 - cleaned_lines_count/original_lines)*100:.1f}%")


if __name__ == "__main__":
    input_file = "/home/dellpro2/wenting/scenario-generation-chatbot/data/md/R171e.md"
    output_file = "/home/dellpro2/wenting/scenario-generation-chatbot/data/md/R171e_cleaned.md"
    
    clean_r171e_for_rag(input_file, output_file)
