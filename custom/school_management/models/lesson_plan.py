from odoo import api, fields, models

class UniversityLessonPlan(models.Model):
    _name = "university.lesson.plan"
    _description = "Lesson Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Title", required=True, tracking=True)
    teacher_id = fields.Many2one(
        "university.teacher", 
        string="Prepared By", 
        required=True, 
        default=lambda self: self._default_teacher()
    )
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    section_id = fields.Many2one("university.class.section", string="Grade/Section", required=True)
    description = fields.Html(string="Lesson Plan")
    share_to = fields.Selection(
        [("all", "All"), ("only_me", "Only Me")], 
        string="Shared To", 
        default="all"
    )
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved")], 
        string="Status", 
        default="draft", 
        tracking=True
    )

    def _default_teacher(self):
        teacher = self.env["university.teacher"].search([("user_id", "=", self.env.uid)], limit=1)
        return teacher.id if teacher else False

    def action_approve(self):
        self.write({"state": "approved"})

    def action_draft(self):
        self.write({"state": "draft"})
