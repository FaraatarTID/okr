from odoo import models, fields


class ProjectTask(models.Model):
    _inherit = 'project.task'

    okr_node_id = fields.Many2one('okr.node', string='Related OKR')
    migration_ref = fields.Char(string='Migration Reference', readonly=True)
