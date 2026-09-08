from collections import Counter

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityEnrollment(models.Model):
    _name = "university.enrollment"
    _description = "University Enrollment"
    _order = "enrollment_date desc, id desc"

    # A student can be enrolled in one subject-based class section at a time
    # (legacy subject enrollment flow keeps one section per record).
    _student_section_unique = models.UniqueIndex(
        "(student_id, section_id)",
        "This student is already enrolled in this class section.",
    )
    # A student can have only ONE active MAJOR enrollment per program, academic
    # year and semester. Subject-based section enrollments (which carry a
    # section_id) are intentionally excluded so the legacy subject workflow is
    # not blocked.
    _student_program_period_unique = models.UniqueIndex(
        "(student_id, program_id, academic_year_id, semester_id) "
        "WHERE status = 'enrolled' AND section_id IS NULL",
        "This student already has an active major enrollment in this program "
        "for the selected academic year and semester.",
    )

    student_id = fields.Many2one(
        "university.student",
        string="Student",
        required=True,
    )
    program_id = fields.Many2one(
        "university.program",
        string="Major / Program",
        required=True,
        index=True,
        help="The major/program the student is enrolled into.",
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
        related="program_id.department_id",
        store=True,
        readonly=True,
        help="Derived from the selected major/program.",
    )
    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
        related="program_id.department_id.faculty_id",
        store=True,
        readonly=True,
        help="Derived from the selected major/program's department.",
    )
    section_id = fields.Many2one(
        "university.class.section",
        string="Class Section",
        domain="[('active', '=', True), ('semester_id', '=', semester_id), '|', ('program_id', '=', program_id), ('subject_id.program_ids', 'in', [program_id])]",
        help="Optional class section / intake cohort for this major enrollment.",
    )
    subject_id = fields.Many2one(
        related="section_id.subject_id",
        string="Subject",
        store=True,
        readonly=True,
        help="Legacy: derived from the class section when a subject-based "
             "section is linked. Not part of the main major enrollment flow.",
    )
    teacher_id = fields.Many2one(
        related="section_id.teacher_id",
        string="Instructor",
        store=True,
        readonly=True,
        help="Legacy: derived from the class section when a subject-based "
             "section is linked. Not part of the main major enrollment flow.",
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        required=True,
    )
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        required=True,
        domain="[('academic_year_id', '=', academic_year_id)]",
    )
    enrollment_date = fields.Date(
        string="Enrollment Date",
        default=fields.Date.context_today,
    )
    status = fields.Selection(
        [
            ("enrolled", "Enrolled"),
            ("completed", "Completed"),
            ("dropped", "Dropped"),
        ],
        string="Status",
        default="enrolled",
    )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_capacity_for_vals(vals_list)
        self._check_active_program_period_duplicates(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        if {"section_id", "status"} & set(vals):
            self._check_capacity_for_vals([
                {
                    "section_id": vals.get("section_id", enrollment.section_id.id),
                    "status": vals.get("status", enrollment.status),
                }
                for enrollment in self
            ], excluded_ids=self.ids)
        return super().write(vals)

    @api.constrains("student_id", "program_id", "section_id")
    def _check_program_section_fit(self):
        for enrollment in self:
            if not self._section_matches_program(enrollment.section_id, enrollment.program_id):
                raise ValidationError(
                    "The selected class section does not belong to the "
                    "chosen major/program."
                )

    @api.constrains("semester_id", "academic_year_id")
    def _check_period_consistency(self):
        for enrollment in self:
            if (
                enrollment.semester_id
                and enrollment.academic_year_id
                and enrollment.semester_id.academic_year_id != enrollment.academic_year_id
            ):
                raise ValidationError(
                    "The selected semester does not belong to the selected "
                    "academic year."
                )

    @api.constrains("section_id", "semester_id", "academic_year_id")
    def _check_section_period_consistency(self):
        for enrollment in self:
            if not enrollment.section_id:
                continue
            sec_sem = enrollment.section_id.semester_id
            if sec_sem and enrollment.semester_id != sec_sem:
                raise ValidationError(
                    "The enrollment semester must match the class section's semester."
                )
            sec_year = sec_sem.academic_year_id if sec_sem else False
            if sec_year and enrollment.academic_year_id != sec_year:
                raise ValidationError(
                    "The enrollment academic year must match the class section's "
                    "academic year."
                )

    @api.onchange("section_id")
    def _onchange_section_id(self):
        if self.section_id:
            sec_sem = self.section_id.semester_id
            if sec_sem:
                self.semester_id = sec_sem
                self.academic_year_id = sec_sem.academic_year_id
            if not self.program_id and self.section_id.program_id:
                self.program_id = self.section_id.program_id
        return self._section_domain_result()

    @api.onchange("program_id")
    def _onchange_program_id(self):
        if self.section_id and not self._section_matches_program(self.section_id, self.program_id):
            self.section_id = False

    @api.onchange("student_id")
    def _onchange_student_id(self):
        if not self.student_id:
            return

        self.program_id = self.student_id.program_id
        self.academic_year_id = self.student_id.academic_year_id
        self.semester_id = self.student_id.current_semester_id
        if self.semester_id:
            self.academic_year_id = self.semester_id.academic_year_id
        if self.section_id and not self._section_matches_program(self.section_id, self.program_id):
            self.section_id = False

    @api.onchange("academic_year_id")
    def _onchange_academic_year_id(self):
        if (
            self.academic_year_id
            and self.semester_id
            and self.semester_id.academic_year_id != self.academic_year_id
        ):
            self.semester_id = False

    @api.onchange("semester_id")
    def _onchange_semester_id(self):
        if self.semester_id and not self.academic_year_id:
            self.academic_year_id = self.semester_id.academic_year_id

    def _section_domain_result(self):
        """Return domain update for section_id based on current filters."""
        domain = [("active", "=", True)]
        if self.semester_id:
            domain.append(("semester_id", "=", self.semester_id.id))
        if self.program_id:
            domain += [
                "|",
                ("program_id", "=", self.program_id.id),
                ("subject_id.program_ids", "in", [self.program_id.id]),
            ]
        return {"domain": {"section_id": domain}}

    def _check_active_program_period_duplicates(self, vals_list):
        """Refuse to create an ACTIVE major enrollment for a student who is
        already actively enrolled in the same program, academic year and
        semester (sectionless major enrollments). The partial unique index
        `_student_program_period_unique` remains as the DB-level backstop."""
        for vals in vals_list:
            if vals.get("status", "enrolled") != "enrolled":
                continue
            if "program_id" not in vals or "academic_year_id" not in vals:
                continue
            if vals.get("section_id"):
                # Subject/section-bound legacy enrollments are unique per section.
                continue
            if not vals.get("student_id"):
                continue
            exists = self.search_count([
                ("student_id", "=", vals["student_id"]),
                ("program_id", "=", vals["program_id"]),
                ("academic_year_id", "=", vals["academic_year_id"]),
                ("semester_id", "=", vals["semester_id"]),
                ("status", "=", "enrolled"),
                ("section_id", "=", False),
            ])
            if exists:
                raise ValidationError(
                    "This student already has an active major enrollment in this "
                    "program for the selected academic year and semester."
                )

    def _check_capacity_for_vals(self, vals_list, excluded_ids=None):
        enrolled_section_ids = [
            vals.get("section_id")
            for vals in vals_list
            if vals.get("section_id") and vals.get("status", "enrolled") == "enrolled"
        ]
        if not enrolled_section_ids:
            return

        section_counts = Counter(enrolled_section_ids)
        sections = self.env["university.class.section"].browse(list(section_counts)).exists()
        sections = sections.filtered("capacity")
        if not sections:
            return

        self.env.cr.execute(
            "SELECT id FROM university_class_section WHERE id IN %s ORDER BY id FOR UPDATE",
            [tuple(sections.ids)],
        )

        excluded_ids = excluded_ids or []
        for section in sections:
            domain = [
                ("section_id", "=", section.id),
                ("status", "=", "enrolled"),
            ]
            if excluded_ids:
                domain.append(("id", "not in", excluded_ids))

            current_count = self.search_count(domain)
            requested_count = section_counts[section.id]
            if current_count + requested_count > section.capacity:
                available = max(section.capacity - current_count, 0)
                raise ValidationError(
                    "Not enough seats in this class section. "
                    f"Available: {available}, requested: {requested_count}."
                )

    def _section_matches_program(self, section, program):
        if not section or not program:
            return True
        if section.program_id:
            return section.program_id == program

        subject = section.subject_id
        if not subject:
            return True
        if subject.program_ids:
            return program in subject.program_ids
        return subject.department_id == program.department_id
