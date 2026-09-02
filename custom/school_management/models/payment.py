from odoo import api, fields, models
from odoo.exceptions import ValidationError


class UniversityPayment(models.Model):
    _name = "university.payment"
    _description = "Student Payment"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Receipt Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: "New",
    )
    student_id = fields.Many2one("university.student", string="Student", required=True)
    fee_id = fields.Many2one("university.fee", string="Fee Invoice", domain="[('student_id', '=', student_id), ('state', '=', 'posted')]")
    
    date = fields.Date(string="Payment Date", default=fields.Date.context_today, required=True)
    currency_id = fields.Many2one("res.currency", string="Currency", compute="_compute_currency_id")
    amount = fields.Float(string="Amount", required=True)
    payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank_transfer", "Bank Transfer"),
            ("credit_card", "Credit Card"),
        ],
        string="Payment Method",
        default="cash",
        required=True,
    )
    reference = fields.Char(string="Transaction Reference")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("canceled", "Canceled"),
        ],
        string="Status",
        default="draft",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("university.payment") or "New"
        return super().create(vals_list)

    def _compute_currency_id(self):
        currency = self.env.company.currency_id
        for payment in self:
            payment.currency_id = currency

    def action_post(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError("Payment amount must be strictly positive.")
            payment.state = "posted"
            if payment.fee_id:
                payment.fee_id._compute_totals()

    def action_cancel(self):
        for payment in self:
            payment.state = "canceled"
            if payment.fee_id:
                payment.fee_id._compute_totals()

    def action_draft(self):
        for payment in self:
            payment.state = "draft"

    def action_print_receipt(self):
        self.ensure_one()
        return self.env.ref(
            "school_management.action_report_university_payment_receipt"
        ).report_action(self)
