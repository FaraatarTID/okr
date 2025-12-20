import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit_app', 'okr_data.json')


def create_project_tasks(env):
    """
    Migration helper to be run inside an Odoo shell.

    Usage in Odoo shell (from Odoo installation folder):
      odoo shell -d <your_db>
      >>> from odoo.addons.okr_tracker.data.create_tasks import create_project_tasks
      >>> create_project_tasks(env)

    This will:
    - Read `okr_data.json` from the streamlit_app folder.
    - For nodes of type INITIATIVE or TASK, create a `project.task`.
    - If the initiative/task has a parent that matches an existing OKR node (by title), link the task's `okr_node_id` to that OKR.

    Note: matching is done by exact title match. Review created tasks afterwards.
    """

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nodes = data.get('nodes', {})

    # Build a mapping of OKR titles to records (objectives/key_results in db)
    okr_model = env['okr.node']
    mapping = {}
    for rec in okr_model.search([]):
        mapping.setdefault(rec.name.strip(), []).append(rec)

    project_task = env['project.task']
    created = 0

    for nid, node in nodes.items():
        ntype = node.get('type', '').upper()
        if ntype in ('INITIATIVE', 'TASK'):
            title = node.get('title') or node.get('name') or 'Untitled'
            desc = node.get('description', '')
            parent_id = node.get('parentId')

            # Try to find related OKR by parent's title
            okr_link = None
            if parent_id:
                parent = nodes.get(parent_id)
                if parent:
                    parent_title = parent.get('title') or parent.get('name')
                    candidates = mapping.get(parent_title.strip(), []) if parent_title else []
                    if candidates:
                        okr_link = candidates[0]

            vals = {
                'name': title,
                'description': desc,
            }
            if okr_link:
                vals['okr_node_id'] = okr_link.id

            # Create the task in the project's default project if available
            # Keep it simple: create task without assigning a project
            project_task.create(vals)
            created += 1

    print('Created', created, 'project.task records from initiatives/tasks in okr_data.json')
