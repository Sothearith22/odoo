from odoo import api, fields, models
from odoo.exceptions import UserError


class BulkMajorEnrollmentWizard(models.TransientModel):
    _name = "university.bulk.enrollment.wizard"
    _description = "Bulk Major Enrollment Wizard"

    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
        domain="[('active', '=', True)]",
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
        domain="[('active', '=', True), ('faculty_id', '=', faculty_id)]",
    )
    program_id = fields.Many2one(
        "university.program",
        string="Major / Program",
        required=True,
        domain="[('active', '=', True), ('department_id', '=', department_id)]",
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        required=True,
        domain="[('active', '=', True)]",
    )
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        required=True,
        domain="[('active', '=', True), ('academic_year_id', '=', academic_year_id)]",
    )
    section_id = fields.Many2one(
        "university.class.section",
        string="Class Section",
        domain="[('active', '=', True), ('semester_id', '=', semester_id), "
               "'|', ('program_id', '=', program_id), "
               "('subject_id.program_ids', 'in', [program_id])]",
        help="Optional cohort/intake section (e.g. GM-Y1-A).",
    )
    student_ids = fields.Many2many(
        "university.student",
        string="Students",
        domain="[('active', '=', True)]",
    )
    eligible_student_ids = fields.Many2many(
        "university.student",
        string="Eligible Students",
        compute="_compute_eligible_students",
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
    selected_student_count = fields.Integer(
        string="Selected Students",
        compute="_compute_selected_student_count",
    )
    eligible_student_count = fields.Integer(
        string="Eligible Student Count",
        compute="_compute_eligible_students",
    )
    available_seats = fields.Integer(
        string="Available Seats",
        compute="_compute_seats",
        help="Shown when a class section with a capacity is selected.",
    )
    capacity_blocked = fields.Boolean(
        string="Capacity Exceeded",
        compute="_compute_seats",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)

        if (
            self.env.context.get("active_model") == "university.student"
            and self.env.context.get("active_ids")
            and "student_ids" in fields_list
        ):
            students = self.env["university.student"].browse(
                self.env.context.get("active_ids")
            ).exists()
            if students:
                values["student_ids"] = [(6, 0, students.ids)]

        section = self.env["university.class.section"].browse(
            values.get("section_id")
        ).exists()
        program = self.env["university.program"].browse(
            values.get("program_id")
        ).exists()

        if section:
            if not program:
                program = section.program_id or section.subject_id.program_ids[:1]
                if program:
                    values["program_id"] = program.id
            if section.semester_id:
                values.setdefault("semester_id", section.semester_id.id)
                values.setdefault("academic_year_id", section.semester_id.academic_year_id.id)

        if program:
            values.setdefault("department_id", program.department_id.id)
            values.setdefault("faculty_id", program.department_id.faculty_id.id)

        return values

    @api.depends("student_ids")
    def _compute_selected_student_count(self):
        for wizard in self:
            wizard.selected_student_count = len(wizard.student_ids)

    @api.depends(
        "faculty_id",
        "department_id",
        "program_id",
        "academic_year_id",
        "semester_id",
        "section_id",
        "status",
    )
    def _compute_eligible_students(self):
        for wizard in self:
            eligible_students = wizard._get_eligible_students()
            wizard.eligible_student_ids = eligible_students
            wizard.eligible_student_count = len(eligible_students)

    @api.depends(
        "section_id",
        "section_id.capacity",
        "section_id.enrollment_ids.status",
        "student_ids",
    )
    def _compute_seats(self):
        for wizard in self:
            wizard.available_seats = 0
            wizard.capacity_blocked = False
            section = wizard.section_id
            if not section or not section.capacity:
                continue
            enrolled = section.enrollment_ids.filtered(
                lambda e: e.status == "enrolled"
            )
            free = max(section.capacity - len(enrolled) - len(wizard.student_ids), 0)
            wizard.available_seats = free if free >= 0 else 0
            wizard.capacity_blocked = len(enrolled) + len(wizard.student_ids) > section.capacity

    @api.onchange("faculty_id")
    def _onchange_faculty_id(self):
        self.department_id = False
        self.program_id = False
        self.section_id = False
        self.student_ids = False
        return self._student_domain()

    @api.onchange("department_id")
    def _onchange_department_id(self):
        self.program_id = False
        self.section_id = False
        self.student_ids = False
        if self.department_id and not self.faculty_id:
            self.faculty_id = self.department_id.faculty_id
        return self._student_domain()

    @api.onchange("program_id")
    def _onchange_program_id(self):
        self.section_id = False
        if self.program_id:
            if not self.department_id:
                self.department_id = self.program_id.department_id
            if not self.faculty_id and self.department_id:
                self.faculty_id = self.department_id.faculty_id
            self.student_ids = False
        else:
            self.student_ids = False
        return self._student_domain()

    @api.onchange("academic_year_id")
    def _onchange_academic_year_id(self):
        self.semester_id = False
        self.section_id = False

    @api.onchange("semester_id")
    def _onchange_semester_id(self):
        self.section_id = False
        if self.semester_id and not self.academic_year_id:
            self.academic_year_id = self.semester_id.academic_year_id

    def _student_domain_list(self):
        """Eligible students: active students already assigned to the chosen
        program, plus students who do not yet have a program (first assignment)."""
        if self.program_id:
            return [
                "&",
                ("active", "=", True),
                "|",
                ("program_id", "=", False),
                ("program_id", "=", self.program_id.id),
            ]
        if self.department_id:
            return [
                "&",
                ("active", "=", True),
                "|",
                ("program_id", "=", False),
                ("department_id", "=", self.department_id.id),
            ]
        return [("active", "=", True)]

    def _student_domain(self):
        return {"domain": {"student_ids": self._student_domain_list()}}

    def _existing_enrollment_domain(self, student_ids=None):
        if not (self.program_id and self.academic_year_id and self.semester_id):
            return [("id", "=", 0)]

        domain = [
            ("program_id", "=", self.program_id.id),
            ("academic_year_id", "=", self.academic_year_id.id),
            ("semester_id", "=", self.semester_id.id),
        ]
        if student_ids:
            domain.insert(0, ("student_id", "in", student_ids))

        if self.section_id:
            # Exclude exact section duplicates and active enrollment in the
            # same cohort period.
            domain += [
                "|",
                ("section_id", "=", self.section_id.id),
                ("status", "=", "enrolled"),
            ]
        else:
            domain.append(("status", "=", "enrolled"))
        return domain

    def _get_eligible_students(self):
        if not self.program_id:
            return self.env["university.student"]

        students = self.env["university.student"].search(self._student_domain_list())
        if not students or not (self.academic_year_id and self.semester_id):
            return students

        existing = self.env["university.enrollment"].search(
            self._existing_enrollment_domain(students.ids)
        )
        return students - existing.mapped("student_id")

    def _reopen_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Bulk Major Enrollment",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_select_all_eligible_students(self):
        self.ensure_one()
        eligible_students = self._get_eligible_students()
        if not eligible_students:
            raise UserError("No eligible students found for the selected filters.")
        self.student_ids = [(6, 0, eligible_students.ids)]
        return self._reopen_wizard()

    def action_clear_students(self):
        self.ensure_one()
        self.student_ids = [(5, 0, 0)]
        return self._reopen_wizard()

    def action_enroll_students(self):
        self.ensure_one()
        if not self.program_id:
            raise UserError("Please select a Major / Program.")
        if not self.student_ids:
            raise UserError("Please select at least one student.")
        if not self.academic_year_id:
            raise UserError("Please select an Academic Year.")
        if not self.semester_id:
            raise UserError("Please select a Semester.")

        # Lock only when capacity must be enforced.
        if self.section_id and self.section_id.capacity:
            self.env.cr.execute(
                "SELECT id FROM university_class_section WHERE id = %s FOR UPDATE",
                [self.section_id.id],
            )

        existing = self.env["university.enrollment"].search(
            self._existing_enrollment_domain(self.student_ids.ids)
        )
        already_ids = existing.mapped("student_id.id")
        students_to_enroll = self.student_ids.filtered(lambda s: s.id not in already_ids)

        if not students_to_enroll:
            raise UserError("All selected students are already enrolled in this "
                            "major/program for the selected period.")

        # Capacity gate uses the same "enrolled" status as the rest of the module.
        if self.section_id and self.section_id.capacity:
            real_enrolled = self.env["university.enrollment"].search_count([
                ("section_id", "=", self.section_id.id),
                ("status", "=", "enrolled"),
            ])
            if real_enrolled + len(students_to_enroll) > self.section_id.capacity:
                free = max(self.section_id.capacity - real_enrolled, 0)
                raise UserError(
                    "Not enough seats in class section '%s'. "
                    "Available: %s, requested: %s."
                    % (self.section_id.name, free, len(students_to_enroll))
                )

        section_id = self.section_id.id if self.section_id else False
        vals_list = [
            {
                "student_id": student.id,
                "program_id": self.program_id.id,
                "section_id": section_id,
                "academic_year_id": self.academic_year_id.id,
                "semester_id": self.semester_id.id,
                "enrollment_date": self.enrollment_date,
                "status": self.status,
            }
            for student in students_to_enroll
        ]
        created = self.env["university.enrollment"].create(vals_list)

        message = f"{len(created)} student(s) enrolled successfully."
        if already_ids:
            message += (
                f" {len(already_ids)} student(s) skipped because they were "
                "already enrolled."
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Enrollment Complete",
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
