import re
from pathlib import Path

def extract_mermaid(file_path):
    """Extract Mermaid diagrams from file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = r'```mermaid\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)
    # Only return the first two diagrams
    return matches[:2]  # This line limits to first two diagrams

def update_readme(diagrams):
    """Update README.md with extracted diagrams."""
    with open('README.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    section_pattern = r'<!-- MERMAID-START -->\n.*?\n<!-- MERMAID-END -->'
    replacement = '<!-- MERMAID-START -->\n'
    
    # Add section headers for each diagram
    diagram_titles = [
        "Agent Interaction Flow",
        "Sequence Flow Example"
    ]
    
    for i, (title, diagram) in enumerate(zip(diagram_titles, diagrams)):
        replacement += f'\n### {title}\n\n'
        replacement += f'```mermaid\n{diagram}\n```\n'
    
    replacement += '\n<!-- MERMAID-END -->'
    
    new_content = re.sub(section_pattern, replacement, content, flags=re.DOTALL)
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(new_content)

def main():
    diagrams = extract_mermaid('ARCHITECTURE.md')
    update_readme(diagrams)

if __name__ == '__main__':
    main()
