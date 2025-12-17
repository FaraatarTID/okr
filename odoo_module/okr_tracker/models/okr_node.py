from odoo import models, fields, api

class OkrNode(models.Model):
    _name = 'okr.node'
    _description = 'OKR Node'

    name = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')
    node_type = fields.Selection([
        ('goal', 'Goal'),
        ('strategy', 'Strategy'),
        ('objective', 'Objective'),
        ('key_result', 'Key Result'),
        ('initiative', 'Initiative'),
        ('task', 'Task'),
    ], string='Type', required=True)
    progress = fields.Float(string='Progress', default=0.0)
    parent_id = fields.Many2one('okr.node', string='Parent')
    child_ids = fields.One2many('okr.node', 'parent_id', string='Children')
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    created_date = fields.Datetime(string='Created', default=fields.Datetime.now)
    is_expanded = fields.Boolean(string='Expanded', default=True)

    @api.constrains('progress')
    def _check_progress(self):
        for record in self:
            if not (0 <= record.progress <= 100):
                raise ValueError('Progress must be between 0 and 100')

    def get_child_types(self):
        type_map = {
            'goal': 'strategy',
            'strategy': 'objective',
            'objective': 'key_result',
            'key_result': 'initiative',
            'initiative': 'task',
        }
        return type_map.get(self.node_type, None)