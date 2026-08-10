import os
from datetime import datetime

# Configure default vault path, can be overridden by environment variable
VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'obsidian_vault'))

def save_to_obsidian(event_id: str, description: str, solution_summary: dict) -> str:
    """Saves the log and solution to the Obsidian vault as a markdown file."""
    os.makedirs(VAULT_PATH, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Event_{event_id}_{timestamp}.md"
    filepath = os.path.join(VAULT_PATH, filename)
    
    # Build markdown content
    content = f"# Event ID: {event_id}\n\n"
    content += f"**Date Saved**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"**Tags**: #eventlog #{event_id}\n\n"
    
    content += f"## Description\n```text\n{description}\n```\n\n"
    
    content += f"## Overview\n{solution_summary.get('overview', '')}\n\n"
    
    content += "## Possible Causes\n"
    for cause in solution_summary.get('causes', []):
        content += f"- {cause}\n"
    content += "\n"
    
    content += "## Troubleshooting Steps\n"
    for idx, step in enumerate(solution_summary.get('steps', [])):
        content += f"{idx + 1}. {step}\n"
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return filepath
