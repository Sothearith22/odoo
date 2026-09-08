from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityClassSection(models.Model):
    _name = "university.class.section"
    _description = "Class Section"

    name = fields.Char(string="Section Name", required=True)
    program_id = fields.Many2one(
        "university.program",
        string="Major / Program",
        help="Optional: link the section to a major/program (program-level "
             "cohort sections such as 'GM-Y1-A'). Preferred over Subject for "
             "the main major enrollment flow.",
    )
    subject_id = fields.Many2one(
        "university.subject",
        string="Subject",
        help="Legacy: set for subject-based class sections. Leave empty for "
             "program-level cohort sections.",
    )
    teacher_id = fields.Many2one(
        "university.teacher",
        string="Instructor",
        help="Legacy: instructor for subject-based class sections.",
    )
    semester_id = fields.Many2one(
        "university.semester", string="Semester", required=True
    )
    classroom_id = fields.Many2one(
        "university.classroom", string="Classroom"
    )
    capacity = fields.Integer(string="Max Capacity", default=30)
    enrollment_ids = fields.One2many(
        "university.enrollment", "section_id", string="Enrolled Students"
    )
    active = fields.Boolean(string="Active", default=True)
    enrolled_student_count = fields.Integer(
        string="Enrolled Count",
        compute="_compute_enrolled_student_count",
    )

    def _compute_enrolled_student_count(self):
        for section in self:
            section.enrolled_student_count = len(
                section.enrollment_ids.filtered(lambda e: e.status == "enrolled")
            )

    @api.constrains("capacity")
    def _check_capacity_positive(self):
        for section in self:
            if section.capacity is not None and section.capacity < 1:
                raise ValidationError(
                    "The class section capacity must be at least 1."
                )

    @api.constrains("program_id", "subject_id")
    def _check_has_program_or_subject(self):
        for section in self:
            if not section.program_id and not section.subject_id:
                raise ValidationError(
                    "A class section must be linked to a Major/Program or a Subject."
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("program_id") and not vals.get("subject_id"):
                raise ValidationError(
                    "A class section must be linked to a Major/Program or a Subject."
                )
        return super().create(vals_list)

    def write(self, vals):
        if "program_id" in vals or "subject_id" in vals:
            for section in self:
                program_id = vals.get("program_id", section.program_id.id)
                subject_id = vals.get("subject_id", section.subject_id.id)
                if not program_id and not subject_id:
                    raise ValidationError(
                        "A class section must be linked to a Major/Program or a Subject."
                    )
        return super().write(vals)

    @api.constrains("teacher_id", "subject_id")
    def _check_teacher_subject(self):
        for section in self:
            if not section.subject_id or not section.teacher_id:
                continue
            if (
                section.subject_id.teacher_ids
                and section.teacher_id not in section.subject_id.teacher_ids
            ):
                raise ValidationError(
                    "The selected instructor is not assigned to teach this subject."
                )

    @api.constrains("program_id", "subject_id")
    def _check_program_subject(self):
        for section in self:
            if not section.program_id or not section.subject_id:
                continue
            subject = section.subject_id
            if subject.program_ids and section.program_id not in subject.program_ids:
                raise ValidationError(
                    "The selected subject does not belong to the chosen major/program."
                )
            if not subject.program_ids and subject.department_id != section.program_id.department_id:
                raise ValidationError(
                    "The selected subject does not belong to the chosen major/program."
                )

    def action_open_bulk_enroll_wizard(self):
        self.ensure_one()
        program = self.program_id
        if not program and self.subject_id.program_ids:
            program = self.subject_id.program_ids[:1]

        return {
            "type": "ir.actions.act_window",
            "name": "Enroll Multiple Students",
            "res_model": "university.bulk.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_section_id": self.id,
                "default_program_id": program.id,
                "default_academic_year_id": self.semester_id.academic_year_id.id,
                "default_semester_id": self.semester_id.id,
            },
        }
