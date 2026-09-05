from odoo import api, fields, models
from odoo.exceptions import ValidationError


def _reindex_org_units(env, org_units):
    """Refresh ``faculty.dean_id`` and ``department.head_id`` pointers for the
    given affected organization units, based on their active assignments."""
    assignment_model = env["university.academic.assignment"]
    dean_faculties = set()
    head_departments = set()

    for role, faculty_id, department_id in org_units or []:
        if role in ("dean", "vice_dean") and faculty_id:
            dean_faculties.add(faculty_id)
        elif role == "department_head" and department_id:
            head_departments.add(department_id)

    for fid in dean_faculties:
        appointee = assignment_model.search(
            [
                ("role", "in", ("dean", "vice_dean")),
                ("faculty_id", "=", fid),
                ("active", "=", True),
            ],
            limit=1,
        ).staff_id
        env["university.faculty"].browse(fid).write({"dean_id": appointee.id or False})

    for did in head_departments:
        appointee = assignment_model.search(
            [
                ("role", "=", "department_head"),
                ("department_id", "=", did),
                ("active", "=", True),
            ],
            limit=1,
        ).staff_id
        env["university.department"].browse(did).write({"head_id": appointee.id or False})


class UniversityAcademicAssignment(models.Model):
    """Reusable appointment record for administrative roles.

    A staff member (``university.teacher``) can hold administrative roles such
    as Dean (of a Faculty) or Head of Department. Keeping these as appointment
    records (instead of separate person models) avoids duplicating people when
    their role changes, and preserves historical assignments with dates.
    """

    _name = "university.academic.assignment"
    _description = "Academic Role Assignment"
    _order = "start_date desc, id desc"

    name = fields.Char(
        string="Reference",
        compute="_compute_name",
        store=True,
    )
    staff_id = fields.Many2one(
        "university.teacher",
        string="Academic Staff",
        required=True,
        ondelete="cascade",
    )
    role = fields.Selection(
        [
            ("dean", "Head of Faculty"),
            ("vice_dean", "Vice Head of Faculty"),
            ("department_head", "Head of Department"),
        ],
        string="Role",
        required=True,
    )
    faculty_id = fields.Many2one(
        "university.faculty",
        string="Faculty",
        domain="[('active', '=', True)]",
    )
    department_id = fields.Many2one(
        "university.department",
        string="Department",
        domain="[('active', '=', True)]",
    )
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    active = fields.Boolean(string="Active", default=True)
    notes = fields.Text(string="Notes")

    _sql_constraints = [
        (
            "unique_active_dean_faculty",
            "UNIQUE(faculty_id) WHERE role = 'dean' AND active",
            "Only one active Head of Faculty is allowed per Faculty.",
        ),
        (
            "unique_active_head_department",
            "UNIQUE(department_id) WHERE role = 'department_head' AND active",
            "Only one active Head of Department is allowed per Department.",
        ),
    ]

    @api.depends("staff_id", "role", "faculty_id", "department_id")
    def _compute_name(self):
        for rec in self:
            who = rec.staff_id.name or "Staff"
            role_label = dict(self._fields["role"].selection).get(rec.role, rec.role)
            scope = " / ".join(
                p for p in (rec.faculty_id.name, rec.department_id.name) if p
            )
            rec.name = f"{who} - {role_label}" + (f" ({scope})" if scope else "")

    @api.constrains("staff_id", "faculty_id", "department_id")
    def _check_org_consistency(self):
        role_labels = dict(self._fields["role"].selection)
        for rec in self:
            label = role_labels.get(rec.role, rec.role)

            if rec.role in ("dean", "vice_dean") and not rec.faculty_id:
                raise ValidationError("A Head of Faculty / Vice Head must be assigned to a Faculty.")
            if rec.role == "department_head" and not rec.department_id:
                raise ValidationError("A Head of Department must be assigned to a Department.")

            staff = rec.staff_id
            if not staff.active:
                raise ValidationError(
                    f"{staff.name} is inactive and cannot hold the '{label}' role."
                )

            if rec.role in ("dean", "vice_dean") and rec.faculty_id:
                if staff.faculty_id and staff.faculty_id != rec.faculty_id:
                    raise ValidationError(
                        f"{staff.name} belongs to {staff.faculty_id.name}, not {rec.faculty_id.name}."
                    )

            if rec.role == "department_head" and rec.department_id:
                if staff.department_id and staff.department_id != rec.department_id:
                    raise ValidationError(
                        f"{staff.name} belongs to {staff.department_id.name}, not {rec.department_id.name}."
                    )

            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(
                    "The appointment start date cannot be after the end date."
                )

    @api.onchange("role")
    def _onchange_role(self):
        if self.role == "department_head":
            self.faculty_id = False
        elif self.role in ("dean", "vice_dean"):
            self.department_id = False

    @api.onchange("department_id")
    def _onchange_department_id(self):
        if self.department_id:
            self.faculty_id = self.department_id.faculty_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._reindex_created()
        return records

    def _reindex_created(self):
        org_units = [
            (rec.role, rec.faculty_id.id, rec.department_id.id)
            for rec in self
            if rec.active
        ]
        if org_units:
            _reindex_org_units(self.env, org_units)

    def write(self, vals):
        before = {
            rec.id: (rec.role, rec.faculty_id.id, rec.department_id.id)
            for rec in self
        }
        res = super().write(vals)
        org_units = list(before.values())
        org_units += [
            (rec.role, rec.faculty_id.id, rec.department_id.id)
            for rec in self
            if rec.active
        ]
        if org_units:
            _reindex_org_units(self.env, org_units)
        return res

    def unlink(self):
        org_units = [
            (rec.role, rec.faculty_id.id, rec.department_id.id) for rec in self
        ]
        res = super().unlink()
        if org_units:
            _reindex_org_units(self.env, org_units)
        return res
