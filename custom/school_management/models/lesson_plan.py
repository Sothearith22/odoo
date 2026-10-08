from odoo import _, fields, models


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
    assignment_count = fields.Integer(
        string="Assignment Count",
        compute="_compute_assignment_count",
    )

    def _default_teacher(self):
        teacher = self.env["university.teacher"].search([("user_id", "=", self.env.uid)], limit=1)
        return teacher.id if teacher else False

    def _compute_assignment_count(self):
        for plan in self:
            count = self.env["university.assignment"].search_count([
                ("section_id", "=", plan.section_id.id),
                ("subject_id", "=", plan.subject_id.id),
            ])
            plan.assignment_count = count

    def action_approve(self):
        self.write({"state": "approved"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_view_assignments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Assignments - %s", self.name),
            "res_model": "university.assignment",
            "view_mode": "kanban,list,form",
            "domain": [
                ("section_id", "=", self.section_id.id),
                ("subject_id", "=", self.subject_id.id),
            ],
            "context": {
                "default_section_id": self.section_id.id,
                "default_subject_id": self.subject_id.id,
                "default_teacher_id": self.teacher_id.id,
            },
        }
