from odoo import _, api, fields, models
from odoo.exceptions import UserError

class ResUsers(models.Model):
    """Extend the user to link them to an academic staff record, enabling
    organizational record rules (a teacher sees their own data, a HOD their
    department, a Dean their faculty)."""
    _inherit = "res.users"
    teacher_id = fields.Many2one(
        "university.teacher",
        string="Academic Staff",
        ondelete="set null",
        help="The academic staff record this user belongs to.",
    )

    _unique_teacher_id = models.UniqueIndex(
        "(teacher_id) WHERE teacher_id IS NOT NULL",
        "An academic staff record can only be linked to one user.",
    )

    def _get_signup_student(self, email):
        normalized_email = (email or "").strip()
        if not normalized_email:
            raise UserError(_("A student email is required to create an account."))

        students = self.env["university.student"].sudo().search(
            [("email", "=ilike", normalized_email)],
            limit=2,
        )
        if not students:
            raise UserError(
                _("No student record was found for this email address. Please contact the administrator.")
            )
        if len(students) > 1:
            raise UserError(
                _("More than one student uses this email address. Please contact the administrator.")
            )

        student = students[0]
        if student.user_id:
            raise UserError(_("This student record is already linked to another login."))
        return student

    @api.model
    def _signup_create_user(self, values):
        if "partner_id" in values:
            return super()._signup_create_user(values)

        email = values.get("email") or values.get("login")
        student = self._get_signup_student(email)
        student_group = self.env.ref("school_management.group_school_student")
        internal_group = self.env.ref("base.group_user")

        signup_values = dict(values)
        # Default student sign-up creates an internal school user so the
        # student can access the backend Student Portal app. Portal-only
        # students remain supported by group_student_portal when assigned
        # explicitly through the normal portal flow.
        signup_values["group_ids"] = [(6, 0, [internal_group.id, student_group.id])]
        signup_values["share"] = False

        user = super()._signup_create_user(signup_values)
        student.write({"user_id": user.id})
        return user

    @api.model
    def _fix_demo_staff_links(self):
        """One-time data migration: make res.users.teacher_id and
        university.teacher.user_id reciprocal for the seeded demo logins,
        pointing each login at the teacher record that actually holds the
        matching active role assignment. Idempotent; no-op when the demo
        records are absent."""
        mapping = [
            ("hod", "Dr. Sarah Jenkins"),
            ("dean", "Prof. Charles Xavier"),
            ("teacher", "Dr. Gregory Hous"),
        ]
        teacher_model = self.env["university.teacher"].sudo()
        users = {
            login: user.sudo()
            for login, _ in mapping
            for user in self.search([("login", "=", login)], limit=1)
        }

        for teacher in teacher_model.search(
            [("user_id", "in", list(users.values()).ids)]
        ):
            teacher.write({"user_id": False})

        for login, teacher_name in mapping:
            user = users.get(login)
            teacher = teacher_model.search(
                [("name", "=", teacher_name)], limit=1
            )
            if not user or not teacher:
                continue
            teacher.write({"user_id": user.id})
            user.write({"teacher_id": teacher.id})
