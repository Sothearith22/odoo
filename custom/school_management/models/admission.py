from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UniversityAdmissionApplication(models.Model):
    _name = "university.admission.application"
    _description = "Admission Application"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "application_date desc, id desc"

    name = fields.Char(
        string="Application Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: "New",
    )
    applicant_name = fields.Char(string="Applicant Name", required=True, tracking=True)
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    address = fields.Text(string="Address")
    date_of_birth = fields.Date(string="Date of Birth")
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
    )
    application_date = fields.Date(
        string="Application Date",
        default=fields.Date.context_today,
        required=True,
    )
    program_id = fields.Many2one(
        "university.program",
        string="Major",
        required=True,
        domain="[('active', '=', True)]",
    )
    department_id = fields.Many2one(
        "university.department",
        related="program_id.department_id",
        string="Department",
        store=True,
        readonly=True,
    )
    faculty_id = fields.Many2one(
        "university.faculty",
        related="program_id.department_id.faculty_id",
        string="Faculty",
        store=True,
        readonly=True,
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
        string="Requested Class Section",
        domain="[('active', '=', True), ('semester_id', '=', semester_id), '|', ('program_id', '=', program_id), ('subject_id.program_ids', 'in', [program_id])]",
    )
    fee_structure_id = fields.Many2one(
        "university.fee.structure",
        string="Fee Structure",
        domain="['|', ('program_id', '=', False), ('program_id', '=', program_id), '|', ('semester_id', '=', False), ('semester_id', '=', semester_id)]",
    )
    student_id = fields.Many2one(
        "university.student",
        string="Student",
        readonly=True,
        copy=False,
    )
    enrollment_id = fields.Many2one(
        "university.enrollment",
        string="Enrollment",
        readonly=True,
        copy=False,
    )
    fee_ids = fields.One2many(
        "university.fee",
        "admission_application_id",
        string="Generated Fees",
    )
    fee_count = fields.Integer(string="Fee Count", compute="_compute_fee_count")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    decision_note = fields.Text(string="Decision Note")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "university.admission.application"
                    )
                    or "New"
                )
        return super().create(vals_list)

    @api.depends("fee_ids")
    def _compute_fee_count(self):
        for application in self:
            application.fee_count = len(application.fee_ids)

    @api.constrains("semester_id", "academic_year_id")
    def _check_period_consistency(self):
        for application in self:
            if (
                application.semester_id
                and application.academic_year_id
                and application.semester_id.academic_year_id
                != application.academic_year_id
            ):
                raise ValidationError(
                    "The selected semester does not belong to the selected academic year."
                )

    @api.constrains("section_id", "program_id", "semester_id")
    def _check_section_consistency(self):
        for application in self:
            section = application.section_id
            if not section:
                continue
            if section.semester_id != application.semester_id:
                raise ValidationError(
                    "The requested section must belong to the selected semester."
                )
            if section.program_id and section.program_id != application.program_id:
                raise ValidationError(
                    "The requested section must belong to the selected program."
                )
            if (
                not section.program_id
                and section.subject_id.program_ids
                and application.program_id not in section.subject_id.program_ids
            ):
                raise ValidationError(
                    "The requested subject section is not offered for the selected program."
                )

    @api.onchange("academic_year_id")
    def _onchange_academic_year_id(self):
        if (
            self.semester_id
            and self.academic_year_id
            and self.semester_id.academic_year_id != self.academic_year_id
        ):
            self.semester_id = False
        self.section_id = False

    @api.onchange("program_id", "semester_id")
    def _onchange_program_period(self):
        self.section_id = False

    def action_submit(self):
        self.write({"state": "submitted"})

    def action_approve(self):
        self.write({"state": "approved"})

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})

    def action_confirm(self):
        for application in self:
            if application.state != "approved":
                raise ValidationError(
                    "Only approved admission applications can be confirmed."
                )
            student = application._get_or_create_student()
            enrollment = application._get_or_create_enrollment(student)
            application._generate_required_fee(student)
            application.write(
                {
                    "student_id": student.id,
                    "enrollment_id": enrollment.id,
                    "state": "confirmed",
                }
            )
            application.message_post(
                body=_(
                    "Admission confirmed. Student %(student)s was enrolled in %(program)s.",
                    student=student.display_name,
                    program=application.program_id.display_name,
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": "Admission Applications",
            "res_model": self._name,
            "view_mode": "list,form",
        }

    def action_view_fees(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Admission Fees",
            "res_model": "university.fee",
            "view_mode": "list,form",
            "domain": [("admission_application_id", "=", self.id)],
            "context": {
                "default_admission_application_id": self.id,
                "default_student_id": self.student_id.id,
            },
        }

    def _get_or_create_student(self):
        self.ensure_one()
        if self.student_id:
            student = self.student_id
            student.write(self._student_update_vals())
            return student

        student = False
        if self.email:
            student = self.env["university.student"].search(
                [("email", "=", self.email)], limit=1
            )
        if student:
            student.write(self._student_update_vals())
            return student

        vals = self._student_update_vals()
        vals.update(
            {
                "name": self.applicant_name,
                "email": self.email,
                "phone": self.phone,
                "address": self.address,
                "date_of_birth": self.date_of_birth,
                "gender": self.gender,
            }
        )
        return self.env["university.student"].create(vals)

    def _student_update_vals(self):
        self.ensure_one()
        return {
            "program_id": self.program_id.id,
            "academic_year_id": self.academic_year_id.id,
            "current_semester_id": self.semester_id.id,
            "status": "active",
            "active": True,
        }

    def _get_or_create_enrollment(self, student):
        self.ensure_one()
        domain = [
            ("student_id", "=", student.id),
            ("program_id", "=", self.program_id.id),
            ("academic_year_id", "=", self.academic_year_id.id),
            ("semester_id", "=", self.semester_id.id),
            ("status", "=", "enrolled"),
        ]
        if self.section_id:
            domain.append(("section_id", "=", self.section_id.id))
        else:
            domain.append(("section_id", "=", False))
        enrollment = self.env["university.enrollment"].search(domain, limit=1)
        if enrollment:
            return enrollment
        return self.env["university.enrollment"].create(
            {
                "student_id": student.id,
                "program_id": self.program_id.id,
                "section_id": self.section_id.id,
                "academic_year_id": self.academic_year_id.id,
                "semester_id": self.semester_id.id,
                "enrollment_date": fields.Date.context_today(self),
                "status": "enrolled",
            }
        )

    def _generate_required_fee(self, student):
        self.ensure_one()
        if not self.fee_structure_id or self.fee_ids:
            return self.env["university.fee"]
        fee = self.env["university.fee"].create(
            self.fee_structure_id._prepare_fee_vals(student, admission=self)
        )
        fee.action_post()
        return fee
