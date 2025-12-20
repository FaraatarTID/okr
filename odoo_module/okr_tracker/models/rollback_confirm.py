from odoo import models, fields, api


class OkrRollbackConfirm(models.TransientModel):
    _name = 'okr.rollback.confirm'
    _description = 'Confirm OKR Migration Rollback'

    migration_log_id = fields.Many2one('okr.migration.log', string='Migration Log', required=True)

    def action_confirm(self):
        self.ensure_one()
        return self.migration_log_id.action_rollback()
