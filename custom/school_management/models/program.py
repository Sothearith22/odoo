from odoo import api, fields, models
from odoo.exceptions import UserError


class UniversityProgram(models.Model):
    _name = "university.program"
    _description = "University Program"

    name = fields.Char(string="Program Name", required=True)
    code = fields.Char(string="Program Code", required=True)
    department_id = fields.Many2one(
        "university.department", string="Department", required=True
    )
    degree_type = fields.Selection(
        [
            ("bachelor", "Bachelor"),
            ("master", "Master"),
            ("doctorate", "Doctorate"),
            ("diploma", "Diploma"),
        ],
        string="Degree Type",
        default="bachelor",
        required=True,
    )
    duration_years = fields.Integer(string="Duration (Years)", default=4)
    total_credits = fields.Integer(string="Total Credits Required", default=120)
    student_ids = fields.One2many(
        "university.student", "program_id", string="Students"
    )
    subject_ids = fields.Many2many(
        "university.subject",
        "university_program_subject_rel",
        "program_id",
        "subject_id",
        string="Subjects"
    )
    subject_count = fields.Integer(
        string="Subjects",
        compute="_compute_subject_count",
    )
    active = fields.Boolean(string="Active", default=True)

    def _compute_subject_count(self):
        for program in self:
            program.subject_count = len(program.subject_ids)

    def action_link_department_subjects(self):
        self.ensure_one()
        subjects = self.env["university.subject"].search([
            ("department_id", "=", self.department_id.id),
            ("program_ids", "=", False),
        ])
        if not subjects:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "No Subjects to Link",
                    "message": "All subjects in this department are already linked to a major.",
                    "type": "warning",
                    "sticky": False,
                },
            }
        subjects.write({"program_ids": [(4, self.id)]})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Subjects Linked",
                "message": f"{len(subjects)} subject(s) linked to {self.name}.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_print_curriculum_report(self):
        """Print the Semester Curriculum PDF for the selected program(s)."""
        return self.env.ref(
            "school_management.action_report_curriculum"
        ).report_action(self)

    @api.model
    def action_print_curriculum_5plus(self):
        """
        Find all active programs with >= 5 active students and print
        their semester curriculum. Called from the Enrollment list toolbar.
        """
        programs = self.search([("active", "=", True)])
        qualified = programs.filtered(
            lambda p: len(
                p.student_ids.filtered(lambda s: s.status == "active")
            ) >= 5
        )
        if not qualified:
            raise UserError(
                "No major currently has 5 or more active students enrolled."
            )
        return self.env.ref(
            "school_management.action_report_curriculum"
        ).report_action(qualified)
