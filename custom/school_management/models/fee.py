from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UniversityFee(models.Model):
    _name = "university.fee"
    _inherit = ["mail.thread"]
    _description = "Student Fee Invoice"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Invoice Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: "New",
    )
    student_id = fields.Many2one("university.student", string="Student", required=True)
    academic_year_id = fields.Many2one("university.academic.year", string="Academic Year")
    semester_id = fields.Many2one("university.semester", string="Semester")
    fee_structure_id = fields.Many2one(
        "university.fee.structure",
        string="Fee Structure",
    )
    admission_application_id = fields.Many2one(
        "university.admission.application",
        string="Admission Application",
        ondelete="set null",
    )
    
    date = fields.Date(string="Invoice Date", default=fields.Date.context_today, required=True)
    due_date = fields.Date(string="Due Date")
    
    currency_id = fields.Many2one("res.currency", string="Currency", compute="_compute_currency_id")
    line_ids = fields.One2many("university.fee.line", "fee_id", string="Fee Lines")
    payment_ids = fields.One2many("university.payment", "fee_id", string="Payments")
    signature_ids = fields.One2many(
        "university.document.signature",
        "fee_id",
        string="Document Signatures",
        groups="base.group_system,school_management.group_school_admin",
    )
    signature_count = fields.Integer(
        string="Signature Count",
        compute="_compute_signature_count",
        groups="base.group_system,school_management.group_school_admin",
    )
    
    total_amount = fields.Float(string="Total Amount", compute="_compute_totals", store=True)
    paid_amount = fields.Float(string="Paid Amount", compute="_compute_totals", store=True)
    balance = fields.Float(string="Balance", compute="_compute_totals", store=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("paid", "Paid"),
            ("canceled", "Canceled"),
        ],
        string="Status",
        default="draft",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("university.fee") or "New"
        return super().create(vals_list)

    def _compute_currency_id(self):
        currency = self.env.company.currency_id
        for fee in self:
            fee.currency_id = currency

    @api.depends(
        "line_ids.amount",
        "payment_ids.amount",
        "payment_ids.state",
    )
    def _compute_totals(self):
        for fee in self:
            total = sum(fee.line_ids.mapped("amount"))
            paid = sum(fee.payment_ids.filtered(lambda p: p.state == "posted").mapped("amount"))
            fee.total_amount = total
            fee.paid_amount = paid
            fee.balance = total - paid

    def _update_state_from_balance(self):
        """Transition fee state based on payment balance.

        Called after payments are posted/canceled so that the state
        always reflects the actual balance without creating a
        compute-dependency cycle on the ``state`` field.
        """
        for fee in self:
            if fee.state == "posted" and fee.balance <= 0 and fee.total_amount > 0:
                fee.state = "paid"
            elif fee.state == "paid" and fee.balance > 0:
                fee.state = "posted"

    def _send_payment_receipt_email(self, payment):
        """Send a payment receipt email for a fee that has just become paid.

        Skips sending (and logs a note in the chatter) when the student has no
        email address configured.
        """
        email = self.student_id.email
        if not email:
            self.message_post(
                body=_(
                    "Payment receipt generated for %(ref)s but NOT emailed: "
                    "the student has no email address configured.",
                    ref=self.name,
                )
            )
            return

        template = self.env.ref(
            "school_management.mail_template_payment_receipt"
        )
        template.send_mail(
            payment.id,
            force_send=False,
            email_layout_xmlid="mail.mail_notification_light",
            email_values={
                "email_to": email,
            },
        )

    @api.depends("signature_ids")
    def _compute_signature_count(self):
        for fee in self:
            fee.signature_count = len(fee.signature_ids)

    def action_request_signature(self):
        self.ensure_one()
        if self.state != "posted":
            raise ValidationError("A signature can only be requested for a posted fee invoice.")

        signature = self.signature_ids.filtered(
            lambda record: record.state == "pending"
        )[:1]
        if not signature:
            signature = self.env["university.document.signature"].create(
                {
                    "student_id": self.student_id.id,
                    "fee_id": self.id,
                }
            )

        return {
            "type": "ir.actions.act_window",
            "name": "Document Signature",
            "res_model": "university.document.signature",
            "view_mode": "form",
            "res_id": signature.id,
            "target": "current",
        }

    def action_view_signatures(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Document Signatures",
            "res_model": "university.document.signature",
            "view_mode": "list,form",
            "domain": [("fee_id", "=", self.id)],
            "context": {
                "default_fee_id": self.id,
                "default_student_id": self.student_id.id,
            },
        }

    def action_post(self):
        for fee in self:
            if not fee.line_ids:
                raise ValidationError("You cannot post a fee invoice without lines.")
            fee.state = "posted"

    def action_cancel(self):
        for fee in self:
            if fee.payment_ids.filtered(lambda p: p.state == "posted"):
                raise ValidationError("You cannot cancel a fee invoice that has posted payments. Cancel the payments first.")
            fee.state = "canceled"
            
    def action_draft(self):
        for fee in self:
            fee.state = "draft"

    def action_print_receipt(self):
        self.ensure_one()
        payment = self.payment_ids.filtered(
            lambda p: p.state == "posted"
        ).sorted("date desc, id desc")[:1]
        if not payment:
            raise ValidationError("No confirmed payment found for this invoice.")
        return self.env.ref(
            "school_management.action_report_university_payment_receipt"
        ).report_action(payment)


class UniversityFeeLine(models.Model):
    _name = "university.fee.line"
    _description = "Fee Line"

    fee_id = fields.Many2one("university.fee", string="Fee Invoice", required=True, ondelete="cascade")
    name = fields.Char(string="Description", required=True)
    amount = fields.Float(string="Amount", required=True)


class UniversityFeeStructure(models.Model):
    _name = "university.fee.structure"
    _description = "Fee Structure"
    _order = "name"

    name = fields.Char(string="Fee Structure", required=True)
    program_id = fields.Many2one(
        "university.program",
        string="Major / Program",
        domain="[('active', '=', True)]",
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        domain="[('active', '=', True)]",
    )
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        domain="[('active', '=', True), ('academic_year_id', '=', academic_year_id)]",
    )
    line_ids = fields.One2many(
        "university.fee.structure.line",
        "structure_id",
        string="Fee Lines",
    )
    total_amount = fields.Float(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
    )
    active = fields.Boolean(string="Active", default=True)

    @api.depends("line_ids.amount")
    def _compute_total_amount(self):
        for structure in self:
            structure.total_amount = sum(structure.line_ids.mapped("amount"))

    def _prepare_fee_vals(self, student, admission=None):
        self.ensure_one()
        return {
            "student_id": student.id,
            "academic_year_id": self.academic_year_id.id
            or (admission.academic_year_id.id if admission else False),
            "semester_id": self.semester_id.id
            or (admission.semester_id.id if admission else False),
            "fee_structure_id": self.id,
            "admission_application_id": admission.id if admission else False,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "name": line.name,
                        "amount": line.amount,
                    },
                )
                for line in self.line_ids
            ],
        }


class UniversityFeeStructureLine(models.Model):
    _name = "university.fee.structure.line"
    _description = "Fee Structure Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    structure_id = fields.Many2one(
        "university.fee.structure",
        string="Fee Structure",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Description", required=True)
    amount = fields.Float(string="Amount", required=True)

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError("Fee structure amounts cannot be negative.")
