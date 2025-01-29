import re
from pathlib import Path

def extract_mermaid(file_path):
    """Extract Mermaid diagrams from file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = r'```mermaid\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)
    return matches

def update_readme(diagrams):
    """Update README.md with extracted diagrams."""
    with open('README.md', 'r', encoding='utf-8') as f:
        content = f.read()
    section_pattern = r'<!-- MERMAID-START -->\n.*?\n<!-- MERMAID-END -->'
    replacement = '<!-- MERMAID-START -->\n'
    for diagram in diagrams:
        replacement += f'```mermaid\n{diagram}\n```\n'
    replacement += '<!-- MERMAID-END -->'
    new_content = re.sub(section_pattern, replacement, content, flags=re.DOTALL)
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(new_content)

def main():
    diagrams = extract_mermaid('ARCHITECTURE.md')
    update_readme(diagrams)

if __name__ == '__main__':
    main()
