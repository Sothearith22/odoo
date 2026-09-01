from odoo import api, fields, models


class Student(models.Model):
    _name = "university.student"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "University Student"

    # Identity
    name = fields.Char(string="Student Name", required=True)
    student_id = fields.Char(string="Student ID", copy=False, index=True)
    image_1920 = fields.Image(string="Photo")
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
    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
        domain="[('faculty_id', '=', faculty_id)]",
    )
    program_id = fields.Many2one(
        "university.program",
        string="Program",
        domain="[('department_id', '=', department_id)]",
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

    def _compute_currency_id(self):
        currency = self.env.company.currency_id
        for rec in self:
            rec.currency_id = currency

    @api.onchange("faculty_id")
    def _onchange_faculty_id(self):
        # Clear department and program if they don't belong to the new faculty
        if self.faculty_id and self.department_id and self.department_id.faculty_id != self.faculty_id:
            self.department_id = False
            self.program_id = False

    @api.onchange("department_id")
    def _onchange_department_id(self):
        # Clear program if it doesn't belong to the new department
        if self.department_id and self.program_id and self.program_id.department_id != self.department_id:
            self.program_id = False
        # Optionally, auto-set faculty if not set or mismatched
        if self.department_id and self.department_id.faculty_id:
            if self.faculty_id != self.department_id.faculty_id:
                self.faculty_id = self.department_id.faculty_id

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

    def action_open_course_registration(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Register Courses",
            "res_model": "university.student.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_student_id": self.id,
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
