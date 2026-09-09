from addons.test_import_export.models.models_export_impex import field
from odoo import models, fields

class DocumentSignature(models.Model):
    _name = 'document.signature'
    _description = 'Document Signature'
    name = fields.Char(required=True)
    student_id = fields.Many2one(comodel_name='student.user', required=True)
    fee_id = fields.Many2one(comodel_name='fee.user', required=True)
    signature = fields.Binary()
    signature_name = fields.Char(required=True)
    state = fields.Selection([('pending','Pending',('signed', 'Signed'))],default='pending')
    signature_on = fields.Datetime()

    def action_signed(self):
        self.write({'state ': 'signed','signed_on':fields.Datetime.now()})
