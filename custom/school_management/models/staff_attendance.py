from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class UniversityStaffAttendance(models.Model):
    _name = "university.staff.attendance"
    _description = "Staff Attendance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, staff_id, id desc"

    staff_id = fields.Many2one(
        "university.teacher",
        string="Staff",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    check_in = fields.Datetime(string="Check-in", tracking=True)
    check_out = fields.Datetime(string="Check-out", tracking=True)
    status = fields.Selection(
        [
            ("present", "Present"),
            ("absent", "Absent"),
            ("late", "Late"),
            ("leave", "On Leave"),
            ("official_duty", "Official Duty"),
            ("half_day", "Half Day"),
        ],
        string="Status",
        required=True,
        default="present",
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Approval Status",
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    remark = fields.Char(string="Remark", tracking=True)
    department_id = fields.Many2one(
        "university.department",
        string="Department",
        related="staff_id.department_id",
        store=True,
        readonly=True,
        index=True,
    )
    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
        related="staff_id.faculty_id",
        store=True,
        readonly=True,
        index=True,
    )
    worked_hours = fields.Float(
        string="Worked Hours",
        compute="_compute_worked_hours",
        store=True,
        readonly=True,
    )
    is_holiday = fields.Boolean(
        string="Is Holiday",
        compute="_compute_is_holiday",
    )
    holiday_name = fields.Char(
        string="Holiday",
        compute="_compute_is_holiday",
    )
    calendar_start = fields.Datetime(
        string="Calendar Start",
        compute="_compute_calendar_dates",
        store=True,
    )
    calendar_stop = fields.Datetime(
        string="Calendar Stop",
        compute="_compute_calendar_dates",
        store=True,
    )

    _staff_date_unique = models.Constraint(
        "unique (staff_id, date)",
        "Only one staff attendance record is allowed per staff member and date.",
    )

    @api.depends("date", "faculty_id")
    def _compute_is_holiday(self):
        for rec in self:
            if not rec.date:
                rec.is_holiday = False
                rec.holiday_name = False
                continue
            holiday = self.env["university.holiday"].search([
                ("date_start", "<=", rec.date),
                ("date_end", ">=", rec.date),
                "|",
                ("faculty_id", "=", False),
                ("faculty_id", "=", rec.faculty_id.id if rec.faculty_id else False),
            ], limit=1)
            rec.is_holiday = bool(holiday)
            rec.holiday_name = holiday.name if holiday else False

    @api.depends("staff_id", "date")
    def _compute_display_name(self):
        for attendance in self:
            staff_name = attendance.staff_id.display_name or _("Staff")
            date = fields.Date.to_string(attendance.date) if attendance.date else _("No date")
            attendance.display_name = _("%(staff)s - %(date)s") % {
                "staff": staff_name,
                "date": date,
            }

    @api.depends("check_in", "check_out")
    def _compute_worked_hours(self):
        for attendance in self:
            if attendance.check_in and attendance.check_out:
                delta = fields.Datetime.to_datetime(attendance.check_out) - fields.Datetime.to_datetime(
                    attendance.check_in
                )
                attendance.worked_hours = delta.total_seconds() / 3600.0
            else:
                attendance.worked_hours = 0.0

    @api.depends("date", "check_in", "check_out", "worked_hours")
    def _compute_calendar_dates(self):
        for rec in self:
            if rec.check_in:
                rec.calendar_start = rec.check_in
            elif rec.date:
                rec.calendar_start = fields.Datetime.to_datetime(f"{rec.date} 08:00:00")
            else:
                rec.calendar_start = False

            if rec.check_out:
                rec.calendar_stop = rec.check_out
            elif rec.calendar_start:
                duration = rec.worked_hours if rec.worked_hours and rec.worked_hours > 0 else 8.0
                rec.calendar_stop = fields.Datetime.add(rec.calendar_start, hours=duration)
            else:
                rec.calendar_stop = False

    @api.constrains("check_in", "check_out")
    def _check_check_out_after_check_in(self):
        for attendance in self:
            if (
                attendance.check_in
                and attendance.check_out
                and attendance.check_out <= attendance.check_in
            ):
                raise ValidationError(_("Check-out must be after check-in."))

    def action_submit(self):
        for attendance in self:
            if attendance.state != "draft":
                raise ValidationError(_("Only draft attendance records can be submitted."))
            if (
                not self.env.su
                and not self.env.user.has_group("school_management.group_school_admin")
                and attendance.staff_id.user_id != self.env.user
            ):
                raise AccessError(_("You are not authorized to submit attendance records for other staff."))
            attendance.write({"state": "submitted"})

    def action_approve(self):
        if not self.env.su and not self.env.user.has_group("school_management.group_school_admin"):
            raise AccessError(_("Only university administrators can approve staff attendance."))
        for attendance in self:
            if attendance.state != "submitted":
                raise ValidationError(_("Only submitted attendance records can be approved."))
            attendance.write({"state": "approved"})

    def action_reject(self):
        if not self.env.su and not self.env.user.has_group("school_management.group_school_admin"):
            raise AccessError(_("Only university administrators can reject staff attendance."))
        for attendance in self:
            if attendance.state != "submitted":
                raise ValidationError(_("Only submitted attendance records can be rejected."))
            attendance.write({"state": "rejected"})

    def action_reset_draft(self):
        if not self.env.su and not self.env.user.has_group("school_management.group_school_admin"):
            raise AccessError(_("Only university administrators can reset attendance records to draft."))
        for attendance in self:
            if attendance.state not in ("approved", "rejected"):
                raise ValidationError(_("Only approved or rejected attendance records can be reset to draft."))
            attendance.write({"state": "draft"})

    @api.model_create_multi
    def create(self, vals_list):
        is_admin = self.env.su or self.env.user.has_group("school_management.group_school_admin")
        teacher_group = self.env.user.has_group("school_management.group_school_teacher")
        for vals in vals_list:
            if not is_admin:
                if vals.get("state") and vals.get("state") != "draft":
                    raise AccessError(_("Only university administrators can set approval status directly."))
                vals["state"] = "draft"
                staff_id = vals.get("staff_id")
                if staff_id and teacher_group:
                    staff = self.env["university.teacher"].browse(staff_id)
                    if staff.user_id != self.env.user:
                        raise AccessError(_("You are only authorized to record your own staff attendance."))
        return super().create(vals_list)

    def write(self, vals):
        is_admin = self.env.su or self.env.user.has_group("school_management.group_school_admin")
        business_fields = {"staff_id", "date", "status", "check_in", "check_out", "remark"}
        has_business_changes = bool(business_fields.intersection(vals.keys()))

        allowed_transitions = {
            "draft": {"draft", "submitted"},
            "submitted": {"submitted", "approved", "rejected"},
            "approved": {"approved", "draft"},
            "rejected": {"rejected", "draft"},
        }

        for record in self:
            # 1. Approved record locking
            if record.state == "approved" and has_business_changes:
                raise UserError(
                    _("Cannot modify an approved attendance record. An administrator must reset it to Draft first.")
                )

            # 2. State transition validation and permission checking
            if "state" in vals:
                new_state = vals["state"]
                valid_targets = allowed_transitions.get(record.state, set())
                if new_state not in valid_targets:
                    raise ValidationError(
                        _("Invalid state transition from %(current)s to %(new)s.",
                          current=record.state,
                          new=new_state)
                    )
                if not is_admin:
                    if new_state in ("approved", "rejected", "draft"):
                        raise AccessError(_("Only university administrators can approve, reject, or reset attendance."))
                    if new_state == "submitted" and record.staff_id.user_id != self.env.user:
                        raise AccessError(_("You are not authorized to submit attendance for other staff."))

            # 3. Non-admin write permissions
            if not is_admin:
                if record.staff_id.user_id != self.env.user:
                    raise AccessError(_("You are not authorized to edit this staff attendance record."))
                if record.state in ("submitted", "approved", "rejected") and has_business_changes:
                    raise UserError(_("Cannot modify attendance records once submitted. Please contact an administrator."))

        return super().write(vals)
