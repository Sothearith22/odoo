from odoo import fields, models


class ResUsers(models.Model):
    """Extend the user to link them to an academic staff record, enabling
    organizational record rules (a teacher sees their own data, a HOD their
    department, a Dean their faculty)."""
    _inherit = "res.users"
    teacher_id = fields.Many2one(
        "university.teacher",
        string="Academic Staff",
        ondelete="set null",
        help="The academic staff record this user belongs to.",
    )
