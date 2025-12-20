import json
import os

# This script is intended to be run inside an Odoo shell or adapted
# to use environment and API to create records. It reads streamlit okr_data.json
# and creates Objective and Key Result records.

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit_app', 'okr_data.json')

with open(DATA_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data.get('nodes', {})

# Simple conversion logic: keep only OBJECTIVE and KEY_RESULT
# Map any other type upwards to the nearest Objective or leave for manual review.

converted = []
for nid, node in nodes.items():
    ntype = node.get('type','').upper()
    if ntype == 'OBJECTIVE' or ntype == 'KEY_RESULT':
        converted.append({
            'name': node.get('title') or node.get('name') or 'Untitled',
            'description': node.get('description',''),
            'node_type': 'objective' if ntype=='OBJECTIVE' else 'key_result',
            'progress': node.get('progress',0),
        })

print('Prepared', len(converted), 'records for import to Odoo. Adapt this script to use Odoo ORM to create records.')
