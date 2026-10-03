import secrets
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class UniversityTranscriptRequest(models.Model):
    _name = "university.transcript.request"
    _description = "Transcript Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    _name_unique = models.Constraint(
        "UNIQUE (name)",
        "The transcript request reference must be unique.",
    )

    def _default_student(self):
        student = self.env["university.student"].search([("user_id", "=", self.env.uid)], limit=1)
        return student.id if student else False

    name = fields.Char(
        string="Request Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: "New",
    )
    student_id = fields.Many2one(
        "university.student",
        string="Student",
        required=True,
        tracking=True,
        index=True,
        default=lambda self: self._default_student(),
    )
    program_id = fields.Many2one(
        "university.program",
        string="Major / Program",
        related="student_id.program_id",
        store=True,
        readonly=True,
        index=True,
    )
    request_type = fields.Selection(
        [
            ("official", "Official Transcript"),
            ("unofficial", "Unofficial Transcript"),
        ],
        string="Request Type",
        default="official",
        required=True,
        tracking=True,
    )
    copies = fields.Integer(
        string="Number of Copies",
        default=1,
        required=True,
    )
    purpose = fields.Selection(
        [
            ("employment", "Employment"),
            ("scholarship", "Scholarship Application"),
            ("transfer", "University Transfer"),
            ("visa", "Visa / Immigration"),
            ("other", "Other"),
        ],
        string="Purpose",
        default="employment",
        required=True,
    )
    purpose_other = fields.Char(string="Purpose Details")
    delivery_method = fields.Selection(
        [
            ("download", "Electronic PDF Download"),
            ("pickup", "In-Person Campus Pickup"),
            ("mail", "Postal Mail"),
        ],
        string="Delivery Method",
        default="download",
        required=True,
    )
    recipient = fields.Char(string="Recipient / Organization")
    delivery_address = fields.Text(string="Delivery Address")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("issued", "Issued"),
            ("delivered", "Delivered"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    reject_reason = fields.Text(
        string="Rejection Reason",
        tracking=True,
    )
    approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
        tracking=True,
    )
    approved_date = fields.Datetime(
        string="Approval Date",
        readonly=True,
        tracking=True,
    )
    transcript_id = fields.Many2one(
        "university.transcript",
        string="Generated Transcript",
        readonly=True,
        tracking=True,
    )
    verification_code = fields.Char(
        string="Verification Code",
        readonly=True,
        copy=False,
    )

    # Optional Fee & Payment Fields
    fee_amount = fields.Monetary(
        string="Processing Fee",
        currency_field="currency_id",
        default=0.0,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    payment_state = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("pending", "Pending Payment"),
            ("paid", "Paid"),
        ],
        string="Payment Status",
        default="not_required",
        tracking=True,
    )

    # Computed helper for holds
    has_holds = fields.Boolean(
        string="Has Academic/Financial Holds",
        compute="_compute_holds",
        store=False,
    )
    holds_summary = fields.Text(
        string="Active Holds",
        compute="_compute_holds",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains("copies")
    def _check_copies(self):
        for record in self:
            if record.copies < 1:
                raise ValidationError("The number of copies must be at least 1.")

    @api.constrains("student_id", "request_type", "state")
    def _check_open_requests(self):
        for record in self:
            if record.state in ("draft", "submitted", "approved"):
                duplicate_count = self.search_count([
                    ("id", "!=", record.id),
                    ("student_id", "=", record.student_id.id),
                    ("request_type", "=", record.request_type),
                    ("state", "in", ("draft", "submitted", "approved")),
                ])
                if duplicate_count:
                    raise ValidationError(
                        f"Student '{record.student_id.name}' already has an active {record.request_type} "
                        "transcript request in progress. Please wait until it is processed or cancelled."
                    )

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("university.transcript.request")
                    or "New"
                )
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Hold Detection
    # -------------------------------------------------------------------------
    def _get_holds(self):
        """Returns a list of hold descriptions that block transcript approval."""
        self.ensure_one()
        holds = []
        if not self.student_id:
            return holds

        # 1. Student Status Hold: Must be active or graduated
        if self.student_id.status not in ("active", "graduated"):
            holds.append(
                f"Student status is '{self.student_id.status or 'Unspecified'}'. "
                "Only Active or Graduated students may receive transcripts."
            )

        # 2. Unpublished report cards hold
        draft_cards = self.env["university.report.card"].search_count([
            ("student_id", "=", self.student_id.id),
            ("state", "=", "draft"),
        ])
        if draft_cards:
            holds.append(
                f"There are {draft_cards} unfinalized/draft semester report card(s) pending approval."
            )

        # For official transcripts, require at least one published/approved report card or transcript
        if self.request_type == "official":
            published_cards = self.env["university.report.card"].search_count([
                ("student_id", "=", self.student_id.id),
                ("state", "in", ("generated", "approved")),
            ])
            existing_transcripts = self.env["university.transcript"].search_count([
                ("student_id", "=", self.student_id.id),
                ("state", "in", ("generated", "approved")),
            ])
            if not published_cards and not existing_transcripts:
                holds.append(
                    "No finalized semester grades or report cards found to generate an official transcript."
                )

        # 3. Finance Holds (Unpaid tuition and fee invoices)
        if hasattr(self.student_id, "fee_balance") and self.student_id.fee_balance > 0.0:
            holds.append(
                f"Outstanding tuition/fee balance of {self.student_id.fee_balance:.2f}. "
                "All outstanding student account balances must be settled before approval."
            )

        unpaid_fees = self.env["university.fee"].search_count([
            ("student_id", "=", self.student_id.id),
            ("state", "=", "posted"),
            ("balance", ">", 0.0),
        ])
        if unpaid_fees:
            holds.append(
                f"Student has {unpaid_fees} posted fee invoice(s) with an overdue balance."
            )

        # 4. Request Fee Hold (when fee_amount is charged)
        if self.fee_amount > 0.0 and self.payment_state != "paid":
            holds.append(
                f"Processing fee of {self.fee_amount:.2f} {self.currency_id.symbol or ''} has not been paid."
            )

        return holds

    @api.depends("student_id", "student_id.status", "student_id.fee_balance", "fee_amount", "payment_state", "request_type")
    def _compute_holds(self):
        for req in self:
            holds = req._get_holds() if req.student_id else []
            req.holds_summary = "\n".join(f"• {h}" for h in holds) if holds else ""
            req.has_holds = bool(holds)

    def _check_registrar_permission(self):
        """Verifies current user belongs to Registrar or Admin role."""
        if not (
            self.env.user.has_group("school_management.group_school_registrar")
            or self.env.user.has_group("school_management.group_school_admin")
            or self.env.is_superuser()
        ):
            raise UserError(
                _("Permission Denied: Only a Registrar or University Administrator can perform this action.")
            )

    # -------------------------------------------------------------------------
    # Actions & Workflow
    # -------------------------------------------------------------------------
    def action_submit(self):
        for req in self:
            if req.state != "draft":
                raise UserError(_("Only draft requests can be submitted."))
            req.with_context(workflow_transition=True).write({"state": "submitted"})
            req.message_post(body=_("Transcript request submitted for administrative review."))

            # Schedule activity for registrar group users
            registrar_group = self.env.ref("school_management.group_school_registrar", raise_if_not_found=False)
            admin_group = self.env.ref("school_management.group_school_admin", raise_if_not_found=False)
            users = registrar_group.user_ids if registrar_group and registrar_group.user_ids else (
                admin_group.user_ids if admin_group and admin_group.user_ids else self.env["res.users"]
            )
            activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            for u in users[:5]:
                try:
                    req.sudo().activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        summary=f"Review Transcript Request: {req.name}",
                        note=f"Student {req.student_id.name} submitted a request for an {req.request_type} transcript ({req.purpose}).",
                        user_id=u.id,
                    )
                except Exception:
                    pass
            req._send_transcript_mail("school_management.mail_template_transcript_request_submitted")

    def _send_transcript_mail(self, template_xmlid):
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if template and self.student_id.email:
            try:
                template.sudo().send_mail(self.id, force_send=False)
            except Exception:
                pass

    def action_approve(self):
        self._check_registrar_permission()
        for req in self:
            if req.state != "submitted":
                raise UserError(_("Only submitted requests can be approved."))

            holds = req._get_holds()
            if holds:
                hold_lines = "\n".join(f"• {h}" for h in holds)
                raise UserError(
                    _("Cannot approve transcript request due to the following active hold(s):\n\n%s", hold_lines)
                )

            req.write({
                "state": "approved",
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            })
            req.action_feedback(feedback=_("Transcript request approved by registrar."))
            req.message_post(body=_("Transcript request approved by %s.", self.env.user.name))
            req._send_transcript_mail("school_management.mail_template_transcript_request_approved")

    def action_reject(self, reason=None):
        self._check_registrar_permission()
        for req in self:
            if req.state not in ("submitted", "approved"):
                raise UserError(_("Only submitted or approved requests can be rejected."))

            if reason:
                req.reject_reason = reason

            if not req.reject_reason:
                raise UserError(_("A rejection reason is required to reject this request."))

            req.write({
                "state": "rejected",
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            })
            req.action_feedback(feedback=_(f"Transcript request rejected: {req.reject_reason}"))
            req.message_post(
                body=_("Transcript request rejected by %s.<br/><b>Reason:</b> %s", self.env.user.name, req.reject_reason)
            )
            req._send_transcript_mail("school_management.mail_template_transcript_request_rejected")

    def action_open_reject_wizard(self):
        self.ensure_one()
        self._check_registrar_permission()
        return {
            "name": _("Reject Transcript Request"),
            "type": "ir.actions.act_window",
            "res_model": "university.transcript.request.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_issue(self):
        self._check_registrar_permission()
        for req in self:
            if req.state != "approved":
                raise UserError(_("A transcript request must be approved before it can be issued."))

            # Ensure holds still do not exist when issuing official transcripts
            if req.request_type == "official":
                holds = req._get_holds()
                if holds:
                    hold_lines = "\n".join(f"• {h}" for h in holds)
                    raise UserError(
                        _("Cannot issue official transcript due to active hold(s):\n\n%s", hold_lines)
                    )

            # Generate or link transcript
            transcript = req.transcript_id
            if not transcript:
                # Search if student already has an approved transcript
                existing_transcript = self.env["university.transcript"].search(
                    [("student_id", "=", req.student_id.id), ("state", "=", "approved")],
                    limit=1,
                    order="id desc",
                )
                if existing_transcript:
                    transcript = existing_transcript
                else:
                    # Create transcript and generate lines from report cards
                    transcript = self.env["university.transcript"].create({
                        "student_id": req.student_id.id,
                    })
                    transcript.action_generate_lines()
                    transcript.action_approve()

            # Generate verification security code
            code = secrets.token_hex(8).upper()
            transcript.verification_code = code

            req.write({
                "state": "issued",
                "transcript_id": transcript.id,
                "verification_code": code,
            })
            req.message_post(
                body=_(
                    "Transcript successfully issued.<br/>"
                    "<b>Transcript Reference:</b> %s<br/>"
                    "<b>Verification Code:</b> <code>%s</code>",
                    transcript.name,
                    code,
                )
            )
            req._send_transcript_mail("school_management.mail_template_transcript_request_issued")

    def action_deliver(self):
        self._check_registrar_permission()
        for req in self:
            if req.state != "issued":
                raise UserError(_("Only issued transcripts can be marked as delivered."))
            req.with_context(workflow_transition=True).write({"state": "delivered"})
            req.message_post(body=_("Transcript marked as delivered to student via %s.", req.delivery_method))

    def action_cancel(self):
        for req in self:
            if req.state not in ("draft", "submitted"):
                raise UserError(_("You can only cancel a request in Draft or Submitted status."))
            req.with_context(workflow_transition=True).write({"state": "cancelled"})
            req.action_feedback(feedback=_("Request cancelled."))
            req.message_post(body=_("Transcript request cancelled."))

    def action_reset_draft(self):
        for req in self:
            if req.state not in ("cancelled", "rejected"):
                raise UserError(_("Only cancelled or rejected requests can be reset to Draft."))
            req.with_context(workflow_transition=True).write({
                "state": "draft",
                "reject_reason": False,
            })
            req.message_post(body=_("Transcript request reset to Draft."))

    def action_feedback(self, feedback):
        """Completes all pending activities on this record."""
        activities = self.activity_ids.filtered(lambda a: a.res_model == self._name)
        if activities:
            activities.action_feedback(feedback=feedback)

    def action_download_transcript(self):
        self.ensure_one()
        if not self.transcript_id:
            raise UserError(_("No transcript has been generated for this request yet."))
        return self.env.ref("school_management.action_report_university_transcript").report_action(self.transcript_id)

    def write(self, vals):
        is_student = self.env.user.has_group("school_management.group_school_student")
        is_registrar = (
            self.env.user.has_group("school_management.group_school_registrar")
            or self.env.user.has_group("school_management.group_school_admin")
            or self.env.is_superuser()
        )
        if is_student and not is_registrar:
            if not self.env.context.get("workflow_transition"):
                restricted_fields = {
                    "state",
                    "approved_by",
                    "approved_date",
                    "reject_reason",
                    "transcript_id",
                    "verification_code",
                }
                if restricted_fields.intersection(vals.keys()):
                    raise AccessError(
                        _("Students are not permitted to modify administrative or workflow fields.")
                    )
            for req in self:
                if req.state not in ("draft",) and not self.env.context.get("workflow_transition"):
                    raise UserError(
                        _("You cannot edit a transcript request once it has been submitted.")
                    )
        return super().write(vals)

    def unlink(self):
        is_registrar = (
            self.env.user.has_group("school_management.group_school_registrar")
            or self.env.user.has_group("school_management.group_school_admin")
            or self.env.is_superuser()
        )
        for req in self:
            if not is_registrar and req.state not in ("draft", "cancelled"):
                raise UserError(
                    _("Only draft or cancelled transcript requests can be deleted.")
                )
        return super().unlink()
