import re
from pathlib import Path
from typing import Optional

def clean_markdown_content(content: str) -> str:
    content = re.sub(r'\[\]\(#[^)]+\)', '', content)
    content = re.sub(r'\[\d+\]\n\(\[\d+\]\(#[^\)]+\)(?:,\[\d+\]\(#[^\)]+\))*\)', '', content)
    content = re.sub(r'\[\[(\d+)\]\]\(#[^)]+\)', r'', content)
    content = re.sub(r'\[\d+\]\(#id\d+\)', '', content)
    content = re.sub(r'\[Image:[^\]]*\]', '', content)
    content = re.sub(r'\[\[source\]\]\([^)]+\)', '', content)
    content = re.sub(r'\[`([^`]+)`\]\([^)]+\)', r'`\1`', content)
    content = re.sub(r'\[([^\[\]]*(?:\[[^\]]*\])?[^\[\]]*)\]\([^)]+\.html[^)]*\)', r'\1', content)
    content = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', content)
    content = re.sub(r'\[([^\]]+)\]\(#[^)]+\)', r'\1', content)
    content = re.sub(r'\[([^\]]+)\]\(reference/[^)]+\)', r'\1', content)
    content = re.sub(r'\[([^\]]+)\]\(glossary\.html[^)]*\)', r'\1', content)
    content = re.sub(r'\[([^\]]+)\]\(modules/[^)]+\)', r'\1', content)
    content = re.sub(r'\[([^\]]+)\]\(\.\./[^)]+\)', r'\1', content)
    content = re.sub(r'\[!\[([^\]]*)\]\([^)]+\)\]\([^)]+\)', r'', content)
    content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'', content)
    content = re.sub(r'`"\)', '`', content)
    content = re.sub(r'\nReferences\n+\[.+?\]\n+.+', '', content, flags=re.DOTALL)
    content = re.sub(r'  +', ' ', content)
    content = re.sub(r' +([.,;:])', r'\1', content)
    content = re.sub(r'\n\n\n+', '\n\n', content)
    
    return content

def process_markdown_file(input_file: Path, output_file: Optional[Path] = None) -> bool:
    try:
        print(f"Processing: {input_file}")
        content = input_file.read_text(encoding='utf-8')
        cleaned_content = clean_markdown_content(content)
        if output_file is None:
            output_file = input_file
        output_file.write_text(cleaned_content, encoding='utf-8')
        print(f"✓ Saved cleaned file to: {output_file}")
        return True
    except Exception as e:
        print(f"✗ Error processing {input_file}: {e}")
        return False

def main():
    markdown_dir = Path(__file__).parent.parent / "data" /"documentation"/ "markdown_test"
    if not markdown_dir.exists():
        print(f"Error: Markdown directory not found: {markdown_dir}")
        return
    md_files = list(markdown_dir.glob("*.md"))
    if not md_files:
        print(f"No markdown files found in: {markdown_dir}")
        return
    print(f"Found {len(md_files)} markdown files in: {markdown_dir}\n")
    success_count = 0
    failure_count = 0
    for md_file in md_files:
        if process_markdown_file(md_file):
            success_count += 1
        else:
            failure_count += 1
        print()
    print("=" * 60)
    print(f"Processing complete!")
    print(f"Successful: {success_count}")
    print(f"Failed: {failure_count}")
    print(f"Total: {len(md_files)}")

if __name__ == "__main__":
    main()
