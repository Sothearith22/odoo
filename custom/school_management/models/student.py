from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class Student(models.Model):
    _name = "university.student"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "University Student"

    # Identity
    name = fields.Char(string="Student Name", required=True)
    student_id = fields.Char(string="Student ID", copy=False, index=True)
    user_id = fields.Many2one(
        "res.users",
        string="Related User",
        ondelete="set null",
        index=True,
        help="The Odoo login for this student.",
    )
    image_1920 = fields.Image(
        string="Photo",
        max_width=1920,
        max_height=1920,
    )
    image_128 = fields.Image(
        string="Photo Thumbnail",
        related="image_1920",
        max_width=128,
        max_height=128,
        store=True,
    )
    date_of_birth = fields.Date(string="Date of Birth")
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
        default="male",
    )

    # Contact Information
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    address = fields.Text(string="Address")
    emergency_contact_name = fields.Char(string="Emergency Contact Name")
    emergency_contact_phone = fields.Char(string="Emergency Contact Phone")

    # Academic Information
    program_id = fields.Many2one(
        "university.program",
        string="Program",
        index=True,
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
        compute="_compute_department_id",
        store=True,
        readonly=False,
        precompute=True,
        help="Derived from the selected program or assigned directly.",
    )
    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
        related="department_id.faculty_id",
        store=True,
        readonly=True,
        help="Derived from the selected department.",
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
    )
    current_semester_id = fields.Many2one(
        "university.semester",
        string="Current Semester",
    )

    # Status
    status = fields.Selection(
        [
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("graduated", "Graduated"),
            ("dropped", "Dropped"),
        ],
        string="Status",
        default="active",
    )
    active = fields.Boolean(string="Active", default=True)

    notes = fields.Text(string="Notes")

    enrollment_ids = fields.One2many(
        "university.enrollment",
        "student_id",
        string="Enrollments",
    )
    admission_application_ids = fields.One2many(
        "university.admission.application",
        "student_id",
        string="Admission Applications",
    )
    submission_ids = fields.One2many(
        "university.assignment.submission",
        "student_id",
        string="Assignment Submissions",
    )
    report_card_ids = fields.One2many(
        "university.report.card",
        "student_id",
        string="Report Cards",
    )
    transcript_ids = fields.One2many(
        "university.transcript",
        "student_id",
        string="Transcripts",
    )
    fee_ids = fields.One2many(
        "university.fee",
        "student_id",
        string="Fee Invoices",
    )
    payment_ids = fields.One2many(
        "university.payment",
        "student_id",
        string="Payments",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        compute="_compute_currency_id",
    )
    fee_total = fields.Monetary(
        string="Fee Total",
        compute="_compute_fee_totals",
        currency_field="currency_id",
    )
    fee_paid = fields.Monetary(
        string="Fees Paid",
        compute="_compute_fee_totals",
        currency_field="currency_id",
    )
    fee_balance = fields.Monetary(
        string="Fee Balance",
        compute="_compute_fee_totals",
        currency_field="currency_id",
    )

    _unique_student_id = models.UniqueIndex(
        "(lower(student_id)) WHERE student_id IS NOT NULL",
        "The Student ID must be unique.",
    )
    _unique_user_id = models.UniqueIndex(
        "(user_id) WHERE user_id IS NOT NULL",
        "A student login can only be linked to one student record.",
    )
    _check_status = models.Constraint(
        "CHECK(status IN ('active', 'suspended', 'graduated', 'dropped'))",
        "Student status must be active, suspended, graduated, or dropped.",
    )

    def _compute_currency_id(self):
        currency = self.env.company.currency_id
        for rec in self:
            rec.currency_id = currency

    def action_view_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Payments",
            "res_model": "university.payment",
            "view_mode": "list,form",
            "domain": [("fee_id.student_id", "=", self.id)],
            "context": {"default_fee_id": False},
        }

    def action_open_enrollment_registration(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Register Enrollments",
            "res_model": "university.student.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_student_id": self.id,
            },
        }

    def action_continue_student(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("school_management.group_school_admin"):
            raise AccessError("Only University Administrators can continue a dropped student.")
        if self.status != "dropped" and self.active:
            raise UserError("Only dropped or inactive students can be continued.")

        return {
            "type": "ir.actions.act_window",
            "name": "Continue Student",
            "res_model": "university.student.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_student_id": self.id,
                "continue_student": True,
            },
        }

    def action_create_user(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("school_management.group_school_admin"):
            raise AccessError(_("Only University Administrators can create student login accounts."))

        email = (self.email or "").strip()
        if not email:
            raise UserError(_("Cannot create account: student %s has no email address.") % self.name)

        if self.user_id:
            raise UserError(_("Student %s is already linked to user account %s.") % (self.name, self.user_id.login))

        Users = self.env["res.users"].sudo()
        student_group = self.env.ref("school_management.group_school_student")
        internal_group = self.env.ref("base.group_user")

        existing_user = Users.search([("login", "=ilike", email)], limit=1)
        if existing_user:
            other_student = self.sudo().search([("user_id", "=", existing_user.id), ("id", "!=", self.id)], limit=1)
            if other_student:
                raise UserError(
                    _("Email %(email)s is already linked to another student: %(student)s.")
                    % {"email": email, "student": other_student.name}
                )
            existing_user.write({
                "group_ids": [(4, internal_group.id), (4, student_group.id)],
            })
            self.sudo().write({"user_id": existing_user.id})
            existing_user.action_reset_password()
        else:
            user = Users.create({
                "name": self.name,
                "login": email,
                "email": email,
                "group_ids": [(6, 0, [internal_group.id, student_group.id])],
            })
            self.sudo().write({"user_id": user.id})
            user.with_context(create_user=1).action_reset_password()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Account Created"),
                "message": _("Login account created for %s with email '%s'. A password setup email was sent.")
                % (self.name, email),
                "type": "success",
                "sticky": False,
            },
        }

    def action_reset_password(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("school_management.group_school_admin"):
            raise AccessError(_("Only University Administrators can reset student passwords."))

        if not self.user_id:
            raise UserError(_("Student %s does not have a linked login account.") % self.name)

        self.user_id.sudo().action_reset_password()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Password Reset"),
                "message": _("A password reset email was sent to %s.") % self.user_id.login,
                "type": "success",
                "sticky": False,
            },
        }

    @api.depends(
        "fee_ids.total_amount",
        "fee_ids.paid_amount",
        "fee_ids.balance",
        "fee_ids.state",
    )
    def _compute_fee_totals(self):
        for rec in self:
            confirmed = rec.fee_ids.filtered(lambda fee: fee.state in ("posted", "paid"))
            rec.fee_total = sum(confirmed.mapped("total_amount"))
            rec.fee_paid = sum(confirmed.mapped("paid_amount"))
            rec.fee_balance = sum(confirmed.mapped("balance"))

    @api.depends("program_id.department_id")
    def _compute_department_id(self):
        for rec in self:
            if rec.program_id:
                rec.department_id = rec.program_id.department_id
            elif not rec.department_id:
                rec.department_id = False

    @api.onchange("program_id")
    def _onchange_program_id(self):
        if self.program_id:
            self.department_id = self.program_id.department_id

    @api.constrains("program_id", "department_id")
    def _check_program_department(self):
        for rec in self:
            if rec.program_id and rec.department_id and rec.program_id.department_id != rec.department_id:
                raise ValidationError(
                    _("The program '%(program)s' does not belong to department '%(department)s'.")
                    % {
                        "program": rec.program_id.display_name,
                        "department": rec.department_id.display_name,
                    }
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            raw_id = vals.get("student_id")
            if not raw_id or not str(raw_id).strip():
                vals["student_id"] = (
                    self.env["ir.sequence"].next_by_code("university.student")
                    or _("New")
                )
            elif isinstance(raw_id, str):
                vals["student_id"] = raw_id.strip()
        return super().create(vals_list)

    def write(self, vals):
        if "student_id" in vals and isinstance(vals["student_id"], str):
            vals["student_id"] = vals["student_id"].strip()
        return super().write(vals)

    def unlink(self):
        for rec in self:
            blocking = []
            if rec.enrollment_ids:
                blocking.append(_("%(count)d enrollment(s)", count=len(rec.enrollment_ids)))
            if rec.report_card_ids:
                blocking.append(_("%(count)d report card(s)", count=len(rec.report_card_ids)))
            if rec.transcript_ids:
                blocking.append(_("%(count)d transcript(s)", count=len(rec.transcript_ids)))
            if blocking:
                raise UserError(
                    _("Cannot delete student '%(student)s' because they have existing records: %(details)s. Archive the student instead.")
                    % {
                        "student": rec.display_name,
                        "details": ", ".join(blocking),
                    }
                )
        return super().unlink()
