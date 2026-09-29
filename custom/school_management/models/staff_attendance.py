from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


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
            ("leave", "On Leave"),
            ("late", "Late"),
        ],
        string="Status",
        required=True,
        default="present",
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

    _staff_date_unique = models.Constraint(
        "unique (staff_id, date)",
        "Only one staff attendance record is allowed per staff member and date.",
    )

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

    @api.constrains("check_in", "check_out")
    def _check_check_out_after_check_in(self):
        for attendance in self:
            if (
                attendance.check_in
                and attendance.check_out
                and attendance.check_out <= attendance.check_in
            ):
                raise ValidationError(_("Check-out must be after check-in."))

    @api.model_create_multi
    def create(self, vals_list):
        if (
            not self.env.su
            and not self.env.user.has_group("school_management.group_school_admin")
            and (
                self.env.user.has_group("school_management.group_school_hod")
                or self.env.user.has_group("school_management.group_school_dean")
            )
        ):
            raise AccessError(_("Head of Department and Head of Faculty users cannot create staff attendance records."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            not self.env.su
            and not self.env.user.has_group("school_management.group_school_admin")
            and (
                self.env.user.has_group("school_management.group_school_hod")
                or self.env.user.has_group("school_management.group_school_dean")
            )
        ):
            raise AccessError(_("Head of Department and Head of Faculty users cannot edit staff attendance records."))
        return super().write(vals)
