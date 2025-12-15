import json
import os

json_path = os.path.join(os.path.dirname(__file__), '../../data/startups_sf.json')
with open(json_path, encoding='utf-8') as f:
    data = json.load(f)

ashby = [c for c in data if 'ashbyhq.com' in c.get('careers_url', '')]

print(f'Total companies: {len(data)}')
print(f'AshbyHQ companies: {len(ashby)}')
print('\nAshbyHQ companies:')
for c in ashby:
    print(f"  • {c['name']}: {c['careers_url']}")

