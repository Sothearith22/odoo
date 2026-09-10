from odoo import api, fields, models

class UniversityServiceHour(models.Model):
    _name = "university.service.hour"
    _description = "Service Hour"
    _order = "create_date desc"

    student_id = fields.Many2one("university.student", string="Student", required=True)
    teacher_id = fields.Many2one("university.teacher", string="Approving Teacher", required=True)
    hours = fields.Float(string="Hours", required=True)
    description = fields.Text(string="Description")
    state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
        string="Status",
        default="pending"
    )

    def action_approve(self):
        self.write({"state": "approved"})

    def action_reject(self):
        self.write({"state": "rejected"})
