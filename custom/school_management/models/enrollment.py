from collections import Counter

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class UniversityEnrollment(models.Model):
    _name = "university.enrollment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "University Enrollment"
    _order = "enrollment_date desc, id desc"

    # A student can be enrolled in one subject-based class section at a time
    # (legacy subject enrollment flow keeps one section per record).
    _student_section_constraint = models.Constraint(
        "unique (student_id, section_id)",
        "This student is already enrolled in this class section.",
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
            ("draft", "Draft"),
            ("to_approve", "To Approve"),
            ("enrolled", "Enrolled"),
            ("withdrawn", "Withdrawn"),
            ("completed", "Completed"),
            ("dropped", "Dropped"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    pending_change = fields.Json(
        string="Pending Change", copy=False, readonly=True,
        help="Values awaiting registrar or administrator approval.",
    )
    possible_duplicate = fields.Boolean(
        string="Possible Duplicate",
        compute="_compute_possible_duplicate",
        search="_search_possible_duplicate",
    )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            self._apply_registration_policy(vals)
        self._check_capacity_for_vals(vals_list)
        self._check_active_program_period_duplicates(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("approval_write"):
            placement_fields = {
                "section_id", "program_id", "semester_id", "academic_year_id",
            }
            if placement_fields & set(vals) or vals.get("status") == "enrolled":
                handled = self.env[self._name]
                for enrollment in self:
                    term = enrollment._term_for_values(vals)
                    if not term:
                        continue
                    if term.academic_year_id.state == "closed":
                        raise ValidationError(
                            "Enrollments cannot be changed for a closed academic year."
                        )
                    today = fields.Date.context_today(enrollment)
                    if term.is_registration_open(today) or term.is_add_drop_open(today):
                        continue
                    if term.add_drop_end and today > term.add_drop_end:
                        pending = {
                            key: vals[key]
                            for key in placement_fields
                            if key in vals
                        }
                        pending["_previous_status"] = enrollment.status
                        super(UniversityEnrollment, enrollment).write({
                            "pending_change": pending,
                            "status": "to_approve",
                        })
                        handled |= enrollment
                        continue
                    raise ValidationError(
                        "Enrollment changes are allowed only during registration or add/drop."
                    )
                self = self - handled
                if not self:
                    return True
        if {"section_id", "status"} & set(vals):
            self._check_capacity_for_vals([
                {
                    "section_id": vals.get("section_id", enrollment.section_id.id),
                    "status": vals.get("status", enrollment.status),
                }
                for enrollment in self
            ], excluded_ids=self.ids)
        return super().write(vals)

    def _term_for_values(self, vals):
        self.ensure_one()
        section = self.env["university.class.section"].browse(
            vals.get("section_id", self.section_id.id)
        ).exists()
        program = self.env["university.program"].browse(
            vals.get("program_id", self.program_id.id)
        ).exists()
        semester = self.env["university.semester"].browse(
            vals.get("semester_id", self.semester_id.id)
        ).exists()
        department = (section.subject_id.department_id if section and section.subject_id
                      else program.department_id if program else self.department_id)
        if not semester or not department:
            return self.env["university.department.term"]
        return self.env["university.department.term"].search([
            ("semester_id", "=", semester.id),
            ("department_id", "=", department.id),
        ], limit=1)

    def _apply_registration_policy(self, vals):
        status = vals.get("status", "draft")
        if status in ("withdrawn", "dropped", "completed"):
            return
        section = self.env["university.class.section"].browse(vals.get("section_id")).exists()
        program = self.env["university.program"].browse(vals.get("program_id")).exists()
        semester = self.env["university.semester"].browse(vals.get("semester_id")).exists()
        department = (section.subject_id.department_id if section and section.subject_id
                      else program.department_id if program else False)
        term = self.env["university.department.term"].search([
            ("semester_id", "=", semester.id if semester else 0),
            ("department_id", "=", department.id if department else 0),
        ], limit=1)
        if not term:
            # Preserve legacy enrollment records until a department schedule
            # has been generated for their semester.
            return
        if term.academic_year_id.state == "closed":
            raise ValidationError("Enrollments cannot be created for a closed academic year.")
        today = fields.Date.context_today(self)
        if term.is_registration_open(today):
            return
        if term.add_drop_end and today > term.add_drop_end:
            vals["status"] = "to_approve"
            return
        raise ValidationError(
            "Enrollment is allowed only during the department registration window."
        )

    def _check_approval_user(self):
        if self.env.su or self.env.user.has_group("school_management.group_school_admin") \
                or self.env.user.has_group("school_management.group_school_registrar"):
            return
        raise AccessError("Only a Registrar or University Administrator can approve enrollments.")

    def action_approve(self):
        self._check_approval_user()
        for enrollment in self.filtered(lambda rec: rec.status == "to_approve"):
            pending = enrollment.pending_change or {}
            values = {
                key: value for key, value in pending.items()
                if not key.startswith("_")
            }
            values.update({"pending_change": False, "status": "enrolled"})
            enrollment.with_context(approval_write=True).write(values)
            enrollment.message_post(body="Enrollment approved by %s." % self.env.user.display_name)
        return True

    def action_reject(self):
        self._check_approval_user()
        for enrollment in self.filtered(lambda rec: rec.status == "to_approve"):
            pending = enrollment.pending_change or {}
            previous_status = pending.get("_previous_status", "dropped")
            enrollment.with_context(approval_write=True).write({
                "pending_change": False,
                "status": previous_status,
            })
            enrollment.message_post(body="Enrollment request rejected by %s." % self.env.user.display_name)
        return True

    def action_withdraw(self):
        for enrollment in self:
            enrollment.status = "withdrawn"
            enrollment.message_post(body="Enrollment withdrawn.")
        return True

    @api.constrains("student_id", "program_id", "academic_year_id", "semester_id", "status")
    def _check_duplicate_program_period(self):
        for enrollment in self:
            if not (
                enrollment.student_id
                and enrollment.program_id
                and enrollment.academic_year_id
                and enrollment.semester_id
            ):
                continue
            if enrollment.status in ("withdrawn", "dropped"):
                continue
            duplicate = self.search([
                ("id", "!=", enrollment.id),
                ("student_id", "=", enrollment.student_id.id),
                ("program_id", "=", enrollment.program_id.id),
                ("academic_year_id", "=", enrollment.academic_year_id.id),
                ("semester_id", "=", enrollment.semester_id.id),
                ("status", "not in", ["withdrawn", "dropped"]),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "This student is already enrolled in the same program, "
                    "academic year and semester. Withdraw the earlier "
                    "enrollment before creating another one."
                )

    def _duplicate_group_domain(self):
        return [("status", "not in", ["withdrawn", "dropped"])]

    def _duplicate_enrollment_ids(self):
        groups = self.read_group(
            self._duplicate_group_domain(),
            ["student_id", "program_id", "academic_year_id", "semester_id"],
            ["student_id", "program_id", "academic_year_id", "semester_id"],
            lazy=False,
        )
        duplicate_ids = []
        for group in groups:
            if group["__count"] <= 1:
                continue
            duplicate_ids.extend(self.search(group["__domain"]).ids)
        return duplicate_ids

    def _compute_possible_duplicate(self):
        duplicate_ids = set(self._duplicate_enrollment_ids())
        for enrollment in self:
            enrollment.possible_duplicate = enrollment.id in duplicate_ids

    def _search_possible_duplicate(self, operator, value):
        duplicate_ids = self._duplicate_enrollment_ids()
        is_positive = (operator in ("=", "==") and value) or (operator in ("!=", "<>") and not value)
        if is_positive:
            return [("id", "in", duplicate_ids or [0])]
        return [("id", "not in", duplicate_ids or [0])]

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
        semester (sectionless major enrollments)."""
        for vals in vals_list:
            if vals.get("status", "draft") != "enrolled":
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
            if vals.get("section_id") and vals.get("status", "draft") == "enrolled"
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
