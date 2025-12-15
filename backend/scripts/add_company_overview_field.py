import json
from pathlib import Path

def add_field_to_json(file_path):
    """Add company_overview field to all entries in a JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    updated = False
    for item in data:
        if 'company_overview' not in item:
            item['company_overview'] = ""
            updated = True
    
    if updated:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return len(data)
    return 0

# Add to all location JSON files
files = [
    'data/startups_remote.json',
    'data/startups_sf.json',
    'data/startups_ny.json',
    'data/startups_boston.json',
    'data/startups_mixed.json'
]

total = 0
for file_path in files:
    path = Path(file_path)
    if path.exists():
        count = add_field_to_json(path)
        total += count
        print(f"✓ {file_path}: {count} entries updated")
    else:
        print(f"✗ {file_path}: not found")

print(f"\nTotal entries updated: {total}")
print("All JSON files now have 'company_overview' field ready for you to fill in!")


