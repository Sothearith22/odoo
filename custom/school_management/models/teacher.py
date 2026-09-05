from odoo import api, fields, models


class Teacher(models.Model):
    _name = "university.teacher"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "University Teacher"

    # Personal Information
    name = fields.Char(string="Teacher Name", required=True)
    teacher_id = fields.Char(string="Teacher ID", copy=False, index=True)
    image_1920 = fields.Image(string="Photo")
    user_id = fields.Many2one(
        "res.users",
        string="Related User",
        ondelete="set null",
        help="Optionally link this academic staff member to their Odoo login for role-based access.",
    )
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )
    date_of_birth = fields.Date(string="Date of Birth")

    # Contact Information
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")
    address = fields.Text(string="Address")

    # Academic Information
    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
        related="department_id.faculty_id",
        store=True,
        readonly=True,
        help="Faculty is derived from the teacher's department.",
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
    )
    position = fields.Selection(
        [
            ("professor", "Professor"),
            ("associate_professor", "Associate Professor"),
            ("assistant_professor", "Assistant Professor"),
            ("lecturer", "Lecturer"),
            ("instructor", "Instructor"),
        ],
        string="Position",
        help="Academic position. Administrative roles (Dean / HOD) are separate appointments.",
    )
    specialization = fields.Char(string="Specialization")
    qualification = fields.Char(string="Qualification")
    hire_date = fields.Date(string="Hire Date")

    # Status
    active = fields.Boolean(string="Active", default=True)

    # Teaching
    subject_ids = fields.Many2many(
        "university.subject",
        "university_teacher_subject_rel",
        "teacher_id",
        "subject_id",
        string="Subjects",
    )
    section_ids = fields.One2many(
        "university.class.section",
        "teacher_id",
        string="Class Sections",
    )

    # Administrative responsibilities (derived from role assignments)
    assignment_ids = fields.One2many(
        "university.academic.assignment",
        "staff_id",
        string="Role Assignments",
    )
    is_dean = fields.Boolean(
        string="Is Dean",
        compute="_compute_admin_roles",
        store=True,
        help="Whether this staff member currently holds an active Dean appointment.",
    )
    is_hod = fields.Boolean(
        string="Is Head of Department",
        compute="_compute_admin_roles",
        store=True,
        help="Whether this staff member currently holds an active HOD appointment.",
    )
    dean_appointment_start = fields.Date(
        string="Dean Appointment Start",
        compute="_compute_admin_appointments",
    )
    dean_appointment_end = fields.Date(
        string="Dean Appointment End",
        compute="_compute_admin_appointments",
    )
    hod_appointment_start = fields.Date(
        string="HOD Appointment Start",
        compute="_compute_admin_appointments",
    )
    hod_appointment_end = fields.Date(
        string="HOD Appointment End",
        compute="_compute_admin_appointments",
    )
    managed_faculty_id = fields.Many2one(
        "university.faculty",
        string="Managed Faculty",
        compute="_compute_admin_appointments",
    )
    managed_department_id = fields.Many2one(
        "university.department",
        string="Managed Department",
        compute="_compute_admin_appointments",
    )

    def _dean_assignment(self, teacher):
        return teacher.assignment_ids.filtered(
            lambda a: a.active and a.role == "dean"
        )[:1]

    def _hod_assignment(self, teacher):
        return teacher.assignment_ids.filtered(
            lambda a: a.active and a.role == "department_head"
        )[:1]

    @api.depends(
        "assignment_ids.role",
        "assignment_ids.active",
        "assignment_ids.faculty_id",
        "assignment_ids.department_id",
        "assignment_ids.start_date",
        "assignment_ids.end_date",
    )
    def _compute_admin_roles(self):
        for teacher in self:
            teacher.is_dean = bool(self._dean_assignment(teacher))
            teacher.is_hod = bool(self._hod_assignment(teacher))

    @api.depends(
        "assignment_ids.role",
        "assignment_ids.active",
        "assignment_ids.faculty_id",
        "assignment_ids.department_id",
        "assignment_ids.start_date",
        "assignment_ids.end_date",
    )
    def _compute_admin_appointments(self):
        for teacher in self:
            dean_asg = self._dean_assignment(teacher)
            head_asg = self._hod_assignment(teacher)

            teacher.dean_appointment_start = dean_asg.start_date
            teacher.dean_appointment_end = dean_asg.end_date
            teacher.managed_faculty_id = dean_asg.faculty_id

            teacher.hod_appointment_start = head_asg.start_date
            teacher.hod_appointment_end = head_asg.end_date
            teacher.managed_department_id = head_asg.department_id

    @api.onchange("department_id")
    def _onchange_department_id(self):
        # Keep the teacher's subjects consistent with the new department:
        # drop subjects that no longer belong to the department.
        if self.department_id and self.subject_ids:
            self.subject_ids = self.subject_ids.filtered(
                lambda s: s.department_id == self.department_id
            )

