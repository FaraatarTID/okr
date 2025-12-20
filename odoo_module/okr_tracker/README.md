OKR Tracker (Odoo module)

Purpose
- Simplified OKR management inside Odoo focused on Objectives and Key Results.
- Initiatives/tasks are migrated into the Project app as `project.task` and linked to OKRs.

Quick install
1. Copy `okr_tracker` directory into your Odoo `addons` path.
2. Restart Odoo server and update the Apps list.
3. Install `OKR Tracker`.

Migration options
- UI wizard: In Odoo, go to OKR Tracker > Import OKR Data and run the wizard to import from `streamlit_app/okr_data.json` in the repository.
- Shell: Run `odoo shell -d <db>` and call `create_project_tasks(env)` or use the wizard code directly.

Notes
- The wizard will create missing Objectives/Key Results (optional), and create `project.task` records for Initiatives/Tasks, attempting to link them to OKRs.
- Titles are matched by exact name; please review the imported records after migration.
