from odoo import models, fields, api
from odoo.exceptions import ValidationError

class OkrNode(models.Model):
    _name = 'okr.node'
    _description = 'OKR Node (Objective / Key Result)'

    name = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')
    # Simplified types: only objectives and key results are managed here.
    node_type = fields.Selection([
        ('objective', 'Objective'),
        ('key_result', 'Key Result'),
    ], string='Type', required=True, default='objective')
    progress = fields.Float(string='Progress', default=0.0)
    # Parent/child kept to model Objective -> Key Result relationship
    parent_id = fields.Many2one('okr.node', string='Parent')
    child_ids = fields.One2many('okr.node', 'parent_id', string='Key Results')
    # Optional linkage to a project for work/tasks handled in the Project app
    project_id = fields.Many2one('project.project', string='Project')
    # Migration reference to track imported records
    migration_ref = fields.Char(string='Migration Reference', readonly=True)
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
            'objective': 'key_result',
        }
        return type_map.get(self.node_type, None)

    @api.constrains('parent_id')
    def _check_parent_allowed(self):
        for record in self:
            if record.parent_id:
                if record.parent_id.node_type != 'objective':
                    raise ValidationError('A Key Result must have an Objective as parent. You cannot add children to a Key Result.')

    @api.model
    def create(self, vals_list):
        # Handle both single-dict and list-of-dicts create calls
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        def extract_parent_id(val):
            pid = val.get('parent_id')
            if not pid:
                return None
            # parent_id might be an int, or a command tuple/list like (6, 0, [ids])
            if isinstance(pid, int):
                return pid
            if isinstance(pid, (list, tuple)):
                # search for first integer id in nested structures
                for item in pid:
                    if isinstance(item, int):
                        return item
                    if isinstance(item, (list, tuple)):
                        for sub in item:
                            if isinstance(sub, int):
                                return sub
            return None

        for vals in vals_list:
            pid = extract_parent_id(vals)
            if pid:
                parent = self.env['okr.node'].browse(pid)
                if parent and parent.node_type != 'objective':
                    raise ValidationError('Cannot add a child to a Key Result. Parent must be an Objective.')
                vals.setdefault('node_type', 'key_result')

        return super().create(vals_list)

    def write(self, vals):
        # If changing parent, validate similarly. Support command-style values.
        if 'parent_id' in vals and vals.get('parent_id'):
            pid = vals.get('parent_id')
            if isinstance(pid, (list, tuple)):
                # extract integer id if present
                found = None
                for item in pid:
                    if isinstance(item, int):
                        found = item
                        break
                    if isinstance(item, (list, tuple)):
                        for sub in item:
                            if isinstance(sub, int):
                                found = sub
                                break
                        if found:
                            break
                pid = found
            if pid:
                parent = self.env['okr.node'].browse(pid)
                if parent and parent.node_type != 'objective':
                    raise ValidationError('Cannot add a child to a Key Result. Parent must be an Objective.')
        return super().write(vals)