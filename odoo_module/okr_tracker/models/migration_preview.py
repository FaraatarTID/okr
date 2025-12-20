from odoo import models, fields
import base64
from datetime import datetime


class OkrMigrationPreview(models.TransientModel):
    _name = 'okr.migration.preview'
    _description = 'OKR Migration Preview'

    okrs_count = fields.Integer(string='Objectives/Key Results to create')
    tasks_count = fields.Integer(string='Tasks to create')
    okrs_sample = fields.Text(string='Sample OKRs (first 20)')
    tasks_sample = fields.Text(string='Sample Tasks (first 20)')

    def action_export_csv(self):
        self.ensure_one()
        lines = []
        lines.append('type,title')
        for l in (self.okrs_sample or '').splitlines():
            lines.append('okr,' + '"%s"' % l.replace('"', '""'))
        for l in (self.tasks_sample or '').splitlines():
            lines.append('task,' + '"%s"' % l.replace('"', '""'))

        csv_data = '\n'.join(lines).encode('utf-8')
        fname = 'okr_migration_preview_%s.csv' % datetime.now().strftime('%Y%m%d%H%M%S')

        attachment = self.env['ir.attachment'].create({
            'name': fname,
            'type': 'binary',
            'datas': base64.b64encode(csv_data),
            'mimetype': 'text/csv',
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
        }
