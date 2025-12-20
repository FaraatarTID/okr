from odoo import models, fields, api
import json
import os


class OkrMigrationWizard(models.TransientModel):
    _name = 'okr.migration.wizard'
    _description = 'Import OKR Data (Streamlit)'

    create_missing_okrs = fields.Boolean(string='Create missing Objectives/Key Results', default=True)
    create_tasks = fields.Boolean(string='Create Project Tasks from Initiatives/Tasks', default=True)
    default_project_id = fields.Many2one('project.project', string='Default Project', help='Assign created tasks to this project (optional)')
    dry_run = fields.Boolean(string='Dry Run (no changes)', default=False)
    rollback_last = fields.Boolean(string='Rollback Last Migration', default=False)

    @api.model
    def _get_data_file(self):
        # Default path relative to module
        module_path = os.path.dirname(__file__)
        # navigate to streamlit_app/okr_data.json from repo layout
        candidates = [
            os.path.join(module_path, '..', '..', 'streamlit_app', 'okr_data.json'),
            os.path.join(module_path, '..', '..', '..', 'streamlit_app', 'okr_data.json'),
        ]
        for p in candidates:
            p = os.path.normpath(p)
            if os.path.exists(p):
                return p
        return None

    def action_run(self):
        """Run migration: create missing OKR nodes and project tasks based on `okr_data.json`.

        The method is intentionally forgiving: it matches existing OKRs by exact title,
        creates missing Objectives/Key Results when requested, and creates `project.task`
        for initiatives/tasks linking them to the related OKR node when possible.
        """
        self.ensure_one()
        data_file = self._get_data_file()
        if not data_file:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': 'OKR Import', 'message': 'Could not find okr_data.json', 'sticky': False},
            }

        # Handle rollback last migration option
        if self.rollback_last:
            last = self.env['okr.migration.log'].search([], order='date desc', limit=1)
            if not last:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {'title': 'OKR Import', 'message': 'No migration log found to rollback', 'sticky': False},
                }
            ok = last.action_rollback()
            if ok:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {'title': 'OKR Import', 'message': 'Rollback completed for %s' % (last.migration_ref or ''), 'sticky': False},
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {'title': 'OKR Import', 'message': 'Rollback failed or nothing to rollback', 'sticky': False},
                }

        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        nodes = data.get('nodes', {})

        # If dry_run, compute preview and show results without creating anything
        if self.dry_run:
            okr_titles = []
            task_titles = []
            for nid, node in nodes.items():
                ntype = node.get('type', '').upper()
                title = node.get('title') or node.get('name') or 'Untitled'
                if ntype in ('OBJECTIVE', 'KEY_RESULT'):
                    okr_titles.append(title)
                elif ntype in ('INITIATIVE', 'TASK'):
                    task_titles.append(title)

            preview = self.env['okr.migration.preview'].create({
                'okrs_count': len(okr_titles),
                'tasks_count': len(task_titles),
                'okrs_sample': '\n'.join(okr_titles[:20]),
                'tasks_sample': '\n'.join(task_titles[:20]),
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'okr.migration.preview',
                'view_mode': 'form',
                'res_id': preview.id,
                'target': 'new',
            }

        okr_model = self.env['okr.node']
        task_model = self.env['project.task']

        # map title -> okr records
        existing = {}
        for r in okr_model.search([]):
            existing.setdefault((r.name or '').strip(), []).append(r)

        created_okrs = 0
        created_tasks = 0
        import time
        migration_ref = None
        if not self.rollback_last:
            migration_ref = time.strftime('migration-%Y%m%d%H%M%S')

        # Helper to create or find OKR by title and type
        def ensure_okr(title, otype):
            nonlocal created_okrs
            title = (title or '').strip()
            if not title:
                return None
            candidates = existing.get(title)
            if candidates:
                for c in candidates:
                    if c.node_type == otype:
                        return c
            if not self.create_missing_okrs:
                return candidates[0] if candidates else None
            vals = {'name': title, 'node_type': otype}
            rec = okr_model.create(vals)
            existing.setdefault(title, []).append(rec)
            created_okrs += 1
            return rec

        # First pass: create OBJECTIVE and KEY_RESULT nodes from data
        for nid, node in nodes.items():
            ntype = node.get('type', '').upper()
            title = node.get('title') or node.get('name')
            if ntype == 'OBJECTIVE':
                rec = ensure_okr(title, 'objective')
                if rec and migration_ref and not self.dry_run:
                    rec.migration_ref = migration_ref
            elif ntype == 'KEY_RESULT':
                # ensure parent objective exists (if parentId points to an objective)
                parent_id = node.get('parentId')
                if parent_id:
                    parent = nodes.get(parent_id)
                    p_title = parent.get('title') if parent else None
                    parent_rec = ensure_okr(p_title, 'objective')
                    kr = ensure_okr(title, 'key_result')
                    if kr and parent_rec:
                        kr.parent_id = parent_rec.id
                    if kr and migration_ref and not self.dry_run:
                        kr.migration_ref = migration_ref
                else:
                    kr = ensure_okr(title, 'key_result')
                    if kr and migration_ref and not self.dry_run:
                        kr.migration_ref = migration_ref

        # Auto-create default project if requested but not provided
        default_project = None
        if self.default_project_id:
            default_project = self.default_project_id
        else:
            # create or find a project named 'OKR Migration' to host created tasks
            pj = self.env['project.project'].search([('name', '=', 'OKR Migration')], limit=1)
            if not pj:
                try:
                    pj = self.env['project.project'].create({'name': 'OKR Migration'})
                except Exception:
                    pj = None
            default_project = pj

        # Second pass: create tasks for INITIATIVE/TASK and link them
        for nid, node in nodes.items():
            ntype = node.get('type', '').upper()
            title = node.get('title') or node.get('name') or 'Untitled'
            desc = node.get('description', '')
            if ntype in ('INITIATIVE', 'TASK') and self.create_tasks:
                parent_id = node.get('parentId')
                okr_link = None
                # Walk up until we find an OBJECTIVE or KEY_RESULT
                cur = node
                while cur and not okr_link:
                    p = cur.get('parentId')
                    if not p:
                        break
                    parent = nodes.get(p)
                    if not parent:
                        break
                    ptype = parent.get('type','').upper()
                    if ptype in ('OBJECTIVE', 'KEY_RESULT'):
                        okr_link = ensure_okr(parent.get('title') or parent.get('name'), 'objective' if ptype=='OBJECTIVE' else 'key_result')
                        break
                    cur = parent

                vals = {'name': title, 'description': desc}
                if default_project:
                    vals['project_id'] = default_project.id
                if okr_link:
                    vals['okr_node_id'] = okr_link.id
                if self.dry_run:
                    created_tasks += 1
                else:
                    t = task_model.create(vals)
                    if migration_ref:
                        t.migration_ref = migration_ref
                    created_tasks += 1

        # create migration log
        try:
            self.env['okr.migration.log'].create({
                'user_id': self.env.uid,
                'migration_ref': migration_ref,
                'okrs_created': created_okrs,
                'tasks_created': created_tasks,
                'notes': 'Imported from streamlit_app/okr_data.json' + (', dry run' if self.dry_run else ''),
            })
        except Exception:
            pass

        message = 'Created %d OKR(s) and %d project task(s)' % (created_okrs, created_tasks)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'OKR Import', 'message': message, 'sticky': False},
        }
