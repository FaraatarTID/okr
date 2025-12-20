from odoo import models, fields
from odoo.exceptions import AccessError


class OkrMigrationLog(models.Model):
    _name = 'okr.migration.log'
    _description = 'OKR Migration Log'

    name = fields.Char(string='Reference', default='OKR Migration')
    user_id = fields.Many2one('res.users', string='User')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    migration_ref = fields.Char(string='Migration Reference')
    okrs_created = fields.Integer(string='OKRs Created', default=0)
    tasks_created = fields.Integer(string='Tasks Created', default=0)
    notes = fields.Text(string='Notes')

    def action_rollback(self):
        """Rollback records created by this migration_ref.

        Only users in the OKR Manager group can perform rollbacks.
        """
        self.ensure_one()
        # permission check
        if not self.env.user.has_group('okr_tracker.group_okr_manager'):
            raise AccessError('Only OKR Manager group members can rollback migrations.')

        ref = self.migration_ref
        if not ref:
            return False

        okr_model = self.env['okr.node']
        task_model = self.env['project.task']

        # Find tasks created by this migration (either by migration_ref or linked OKRs)
        tasks_by_ref = task_model.search([('migration_ref', '=', ref)])
        okrs = okr_model.search([('migration_ref', '=', ref)])
        tasks_by_okr = task_model.search([('okr_node_id', 'in', okrs.ids)]) if okrs else self.env['project.task']

        # Combine and unlink tasks first
        tasks_to_unlink = (tasks_by_ref | tasks_by_okr).filtered(lambda r: r.exists())
        tasks_deleted = 0
        if tasks_to_unlink:
            tasks_deleted = len(tasks_to_unlink)
            tasks_to_unlink.unlink()

        # Then unlink OKR nodes
        okrs_to_unlink = okrs.filtered(lambda r: r.exists())
        okrs_deleted = 0
        if okrs_to_unlink:
            okrs_deleted = len(okrs_to_unlink)
            okrs_to_unlink.unlink()

        # Record rollback in a new log entry
        try:
            self.env['okr.migration.log'].create({
                'user_id': self.env.uid,
                'migration_ref': ref,
                'okrs_created': -okrs_deleted,
                'tasks_created': -tasks_deleted,
                'notes': 'Rollback of %s: removed %d OKR(s) and %d task(s)' % (ref, okrs_deleted, tasks_deleted),
            })
        except Exception:
            pass

        return True
