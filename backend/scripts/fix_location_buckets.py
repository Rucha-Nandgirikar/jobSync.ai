import json
from pathlib import Path

# SF should only have the explicitly listed ones (41 total)
# Everything else with unknown/mixed location goes to "mixed" bucket

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Load all current files
remote = load_json('data/startups_remote.json')
sf = load_json('data/startups_sf.json')
ny = load_json('data/startups_ny.json')
boston = load_json('data/startups_boston.json')

print(f"Before cleanup:")
print(f"  Remote: {len(remote)}")
print(f"  SF: {len(sf)}")
print(f"  NY: {len(ny)}")
print(f"  Boston: {len(boston)}")

# SF should be: original 23 from CSV + 15 manually added + 3 more = 41
# But user said "Debut to Tempo" and "Arcade to Descript" are "don't know" - so move those to mixed

# Identify SF companies (explicitly marked SF in original data)
# Keep only the ones that were explicitly SF, not the "don't know" ones
explicit_sf_names = {
    "Pylon", "Relace", "Datacurve", "Unify", "FurtherAI", "Assort Health", "Cal.com Inc.", "Osmind",
    "Vitalize", "BlueAlpha", "SafetyKit", "Zams", "Truewind", "Metaview", "Mintlify", "Salient",
    "Deepnote", "Giga", "Rootly", "Rattle", "Pocus", "AtoB", "Density",
    # Manually added 15
    "Hedra", "OpenMind", "Martian", "FERMÀT", "Miter", "StackAI", "Hanomi", "Polycam",
    "Watershed", "Blok", "Netic", "Shepherd", "Heirloom", "Pulley", "Layer"
}

sf_keep = [s for s in sf if s['name'] in explicit_sf_names]

# Everything else from SF that's not explicitly SF goes to "mixed"
mixed_from_sf = [s for s in sf if s['name'] not in explicit_sf_names]
for m in mixed_from_sf:
    m['location_type'] = 'mixed'

# Companies from remote that have empty notes/descriptions (likely "don't know") -> mixed
mixed_from_remote = []
remote_keep = []
for r in remote:
    # If it's clearly remote (has "remote" in notes or is explicitly remote), keep it
    notes_lower = (r.get('notes') or '').lower()
    if 'remote' in notes_lower or len(r.get('notes', '')) > 10:  # Has description
        remote_keep.append(r)
    else:
        # Likely "don't know" - move to mixed
        r['location_type'] = 'mixed'
        mixed_from_remote.append(r)

# Combine all mixed
mixed = mixed_from_sf + mixed_from_remote

print(f"\nAfter cleanup:")
print(f"  Remote: {len(remote_keep)}")
print(f"  SF: {len(sf_keep)}")
print(f"  NY: {len(ny)}")
print(f"  Boston: {len(boston)}")
print(f"  Mixed: {len(mixed)}")

# Save updated files
save_json(remote_keep, 'data/startups_remote.json')
save_json(sf_keep, 'data/startups_sf.json')
save_json(ny, 'data/startups_ny.json')
save_json(boston, 'data/startups_boston.json')
save_json(mixed, 'data/startups_mixed.json')

print("\n✓ Created startups_mixed.json for companies with unknown/mixed locations")


