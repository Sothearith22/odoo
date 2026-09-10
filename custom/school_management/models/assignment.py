from odoo import api, fields, models

class UniversityAssignment(models.Model):
    _name = "university.assignment"
    _description = "Assignment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Assignment Name", required=True, tracking=True)
    teacher_id = fields.Many2one(
        "university.teacher", 
        string="Prepared By", 
        required=True, 
        default=lambda self: self._default_teacher()
    )
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    section_id = fields.Many2one("university.class.section", string="Grade/Section", required=True)
    assignment_type = fields.Selection(
        [("class", "Class Assignment"), ("student", "Student Assignment")],
        string="Assignment Type",
        required=True,
        default="class"
    )
    description = fields.Html(string="Description")
    due_date = fields.Date(string="Due Date")
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved")], 
        string="Status", 
        default="draft", 
        tracking=True
    )
    
    student_id = fields.Many2one(
        "university.student", 
        string="Student", 
        help="Specific student if this is a Student Assignment"
    )

    def _default_teacher(self):
        teacher = self.env["university.teacher"].search([("user_id", "=", self.env.uid)], limit=1)
        return teacher.id if teacher else False

    def action_approve(self):
        self.write({"state": "approved"})

    def action_draft(self):
        self.write({"state": "draft"})
