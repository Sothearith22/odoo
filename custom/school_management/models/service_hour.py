from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

class UniversityServiceHour(models.Model):
    _name = "university.service.hour"
    _description = "Service Hour"
    _order = "create_date desc"

    student_id = fields.Many2one("university.student", string="Student", required=True)
    teacher_id = fields.Many2one("university.teacher", string="Approving Teacher", required=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    academic_year_id = fields.Many2one("university.academic.year", string="Academic Year")
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        domain="[('academic_year_id', '=', academic_year_id)]",
    )
    hours = fields.Float(string="Hours", required=True)
    description = fields.Text(string="Description")
    state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
        string="Status",
        default="pending",
    )

    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    approved_date = fields.Date(string="Approved Date", readonly=True, copy=False)

    @api.constrains("hours")
    def _check_hours(self):
        for service_hour in self:
            if service_hour.hours <= 0:
                raise ValidationError(_("Service hours must be greater than zero."))

    @api.constrains("semester_id", "academic_year_id")
    def _check_period(self):
        for service_hour in self:
            if (
                service_hour.semester_id
                and service_hour.academic_year_id
                and service_hour.semester_id.academic_year_id != service_hour.academic_year_id
            ):
                raise ValidationError(_("The semester must belong to the selected academic year."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and self.env.user.has_group("school_management.group_school_student"):
            student = self.env.user.student_id
            for vals in vals_list:
                if not student or vals.get("student_id") != student.id:
                    raise AccessError(_("Students can only submit service hours for themselves."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and self.env.user.has_group("school_management.group_school_student"):
            student = self.env.user.student_id
            if any(record.student_id != student for record in self):
                raise AccessError(_("Students can only edit their own service hours."))
            if any(record.state != "pending" for record in self):
                raise AccessError(_("Only pending service-hour requests can be edited."))
            if vals.get("student_id") and vals["student_id"] != student.id:
                raise AccessError(_("Students cannot assign service hours to another student."))
            if any(key in vals for key in ("state", "approved_by", "approved_date")):
                raise AccessError(_("Students cannot approve or reject service hours."))
        return super().write(vals)

    def _check_approval_access(self):
        if self.env.su or self.env.user.has_group("school_management.group_school_admin"):
            return
        if not self.env.user.has_group("school_management.group_school_teacher"):
            raise AccessError(_("Only an administrator or teacher can approve service hours."))
        if any(record.teacher_id.user_id != self.env.user for record in self):
            raise AccessError(_("A teacher can approve only their assigned service hours."))

    def action_approve(self):
        self._check_approval_access()
        if any(record.state != "pending" for record in self):
            raise ValidationError(_("Only pending service hours can be approved."))
        self.write({
            "state": "approved",
            "approved_by": self.env.user.id,
            "approved_date": fields.Date.context_today(self),
        })

    def action_reject(self):
        self._check_approval_access()
        if any(record.state != "pending" for record in self):
            raise ValidationError(_("Only pending service hours can be rejected."))
        self.write({
            "state": "rejected",
            "approved_by": self.env.user.id,
            "approved_date": fields.Date.context_today(self),
        })
