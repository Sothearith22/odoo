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
    
    date = fields.Date(string="Invoice Date", default=fields.Date.context_today, required=True)
    due_date = fields.Date(string="Due Date")
    
    currency_id = fields.Many2one("res.currency", string="Currency", compute="_compute_currency_id")
    line_ids = fields.One2many("university.fee.line", "fee_id", string="Fee Lines")
    payment_ids = fields.One2many("university.payment", "fee_id", string="Payments")
    signature_ids = fields.One2many(
        "university.document.signature",
        "fee_id",
        string="Document Signatures",
    )
    signature_count = fields.Integer(
        string="Signature Count",
        compute="_compute_signature_count",
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
        "state",
    )
    def _compute_totals(self):
        for fee in self:
            total = sum(fee.line_ids.mapped("amount"))
            paid = sum(fee.payment_ids.filtered(lambda p: p.state == "posted").mapped("amount"))
            fee.total_amount = total
            fee.paid_amount = paid
            fee.balance = total - paid

            if fee.state == "posted" and fee.balance <= 0 < total:
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
