import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class UniversityDashboard(models.Model):
    _name = "school.dashboard"
    _description = "University Dashboard"

    name = fields.Char(string="Dashboard", default="University Dashboard")

    student_count = fields.Integer(string="Students", compute="_compute_counts")
    active_student_count = fields.Integer(string="Active Students", compute="_compute_counts")
    suspended_student_count = fields.Integer(string="Suspended Students", compute="_compute_counts")
    graduated_student_count = fields.Integer(string="Graduated Students", compute="_compute_counts")
    dropped_student_count = fields.Integer(string="Dropped Students", compute="_compute_counts")

    teacher_count = fields.Integer(string="Teachers", compute="_compute_counts")
    faculty_count = fields.Integer(string="Faculties", compute="_compute_counts")
    department_count = fields.Integer(string="Departments", compute="_compute_counts")
    program_count = fields.Integer(string="Programs", compute="_compute_counts")
    subject_count = fields.Integer(string="Subjects", compute="_compute_counts")
    classroom_count = fields.Integer(string="Classrooms", compute="_compute_counts")
    section_count = fields.Integer(string="Class Sections", compute="_compute_counts")
    enrollment_count = fields.Integer(string="Enrollments", compute="_compute_counts")
    fee_count = fields.Integer(string="Fee Invoices", compute="_compute_counts")
    payment_count = fields.Integer(string="Payments", compute="_compute_counts")

    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id")
    total_unpaid_fees = fields.Monetary(string="Unpaid Fees", compute="_compute_counts", currency_field="currency_id")
    total_paid_fees = fields.Monetary(string="Paid Fees", compute="_compute_counts", currency_field="currency_id")
    total_scholarships = fields.Monetary(string="Scholarships", compute="_compute_counts", currency_field="currency_id")

    def _compute_currency_id(self):
        currency = self.env.company.currency_id
        for rec in self:
            rec.currency_id = currency

    def _can_read(self, model):
        """Whether the current user may read the given model (no sudo)."""
        try:
            return self.env[model].browse().has_access("read")
        except Exception:
            _logger.exception(
                "Dashboard access check failed for user %s (%s) on model %s",
                self.env.user.id,
                self.env.user.login,
                model,
            )
            return False

    def _safe_count(self, model, domain=None):
        """Count records the current user is allowed to see (via ACL + record rules)."""
        try:
            if not self._can_read(model):
                _logger.info(
                    "Dashboard count skipped for user %s (%s): no read access on %s",
                    self.env.user.id,
                    self.env.user.login,
                    model,
                )
                return 0
            return self.env[model].search_count(domain or [])
        except Exception:
            _logger.exception(
                "Dashboard count failed for user %s (%s) on model %s",
                self.env.user.id,
                self.env.user.login,
                model,
            )
            return 0

    def _safe_sum(self, model, domain, field):
        try:
            if not self._can_read(model):
                _logger.info(
                    "Dashboard sum skipped for user %s (%s): no read access on %s",
                    self.env.user.id,
                    self.env.user.login,
                    model,
                )
                return 0.0
            records = self.env[model].search(domain or [])
            return sum(records.mapped(field) or [0.0]) or 0.0
        except Exception:
            _logger.exception(
                "Dashboard sum failed for user %s (%s) on model %s.%s",
                self.env.user.id,
                self.env.user.login,
                model,
                field,
            )
            return 0.0

    @api.depends()
    def _compute_counts(self):
        for rec in self:
            rec.student_count = self._safe_count("university.student")
            rec.active_student_count = self._safe_count(
                "university.student", [("status", "=", "active")]
            )
            rec.suspended_student_count = self._safe_count(
                "university.student", [("status", "=", "suspended")]
            )
            rec.graduated_student_count = self._safe_count(
                "university.student", [("status", "=", "graduated")]
            )
            rec.dropped_student_count = self._safe_count(
                "university.student", [("status", "=", "dropped")]
            )

            rec.teacher_count = self._safe_count("university.teacher")
            rec.faculty_count = self._safe_count("university.faculty")
            rec.department_count = self._safe_count("university.department")
            rec.program_count = self._safe_count("university.program")
            rec.subject_count = self._safe_count("university.subject")
            rec.classroom_count = self._safe_count("university.classroom")
            rec.section_count = self._safe_count("university.class.section")
            rec.enrollment_count = self._safe_count("university.enrollment")
            rec.fee_count = self._safe_count("university.fee")
            rec.payment_count = self._safe_count("university.payment")

            # Financials — only aggregated from records the current user may see.
            rec.total_unpaid_fees = self._safe_sum(
                "university.fee",
                [("state", "in", ("posted", "paid"))],
                "balance",
            )
            rec.total_paid_fees = self._safe_sum(
                "university.payment",
                [("state", "=", "posted")],
                "amount",
            )

            # Placeholder until phase 5 part 2
            rec.total_scholarships = 0.0

    @api.model
    def get_chart_data(self):
        program_data = []
        status_data = []
        recent_payments = []

        if self._can_read("university.student"):
            try:
                program_rows = self.env["university.student"]._read_group(
                    [("active", "=", True), ("program_id", "!=", False)],
                    ["program_id"],
                    ["__count"],
                    order="__count DESC",
                    limit=10,
                )
                can_read_program = self._can_read("university.program")
                program_counts = {}
                for program, count in program_rows:
                    label = (
                        program.display_name
                        if program and can_read_program
                        else ("Other" if not program else "Restricted")
                    )
                    program_counts[label] = program_counts.get(label, 0) + count
                program_data = list(program_counts.items())

                status_rows = self.env["university.student"]._read_group(
                    [], ["status"], ["__count"]
                )
                status_data = [
                    (status or "unknown", count) for status, count in status_rows
                ]
            except Exception:
                _logger.exception(
                    "Dashboard student charts failed for user %s (%s)",
                    self.env.user.id,
                    self.env.user.login,
                )

        if self._can_read("university.payment"):
            try:
                recent_payments = self.env["university.payment"].search_read(
                    [("state", "=", "posted")],
                    ["name", "amount", "date", "student_id", "currency_id"],
                    limit=5,
                    order="date desc, id desc",
                )
                for p in recent_payments:
                    p["student_name"] = (
                        p["student_id"][1] if p.get("student_id") else "Unknown"
                    )
            except Exception:
                _logger.exception(
                    "Dashboard payment chart failed for user %s (%s)",
                    self.env.user.id,
                    self.env.user.login,
                )

        return {
            "program_distribution": {
                "labels": [row[0] for row in program_data],
                "data": [row[1] for row in program_data],
            },
            "student_status": {
                "labels": [row[0].capitalize() for row in status_data],
                "data": [row[1] for row in status_data],
            },
            "recent_payments": recent_payments,
        }

    def action_open_students(self):
        return self._open_action("university.student")

    def action_open_teachers(self):
        return self._open_action("university.teacher")

    def action_open_faculties(self):
        return self._open_action("university.faculty")

    def action_open_departments(self):
        return self._open_action("university.department")

    def action_open_programs(self):
        return self._open_action("university.program")

    def action_open_subjects(self):
        return self._open_action("university.subject")

    def action_open_classrooms(self):
        return self._open_action("university.classroom")

    def action_open_sections(self):
        return self._open_action("university.class.section")

    def action_open_enrollments(self):
        return self._open_action("university.enrollment")

    def action_open_fees(self):
        return self._open_action("university.fee")

    def action_open_unpaid_fees(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Unpaid Fees",
            "res_model": "university.fee",
            "view_mode": "list,form",
            "domain": [
                ("state", "=", "posted"),
                ("balance", ">", 0),
            ],
            "target": "current",
        }

    def action_open_payments(self):
        return self._open_action("university.payment")

    def action_open_academic_years(self):
        return self._open_action("university.academic.year")

    def action_create_student(self):
        return {
            "type": "ir.actions.act_window",
            "name": "New Student",
            "res_model": "university.student",
            "view_mode": "form",
            "target": "current",
        }

    def action_create_enrollment(self):
        return {
            "type": "ir.actions.act_window",
            "name": "New Enrollment",
            "res_model": "university.enrollment",
            "view_mode": "form",
            "target": "current",
        }

    def action_create_fee(self):
        return {
            "type": "ir.actions.act_window",
            "name": "New Fee Invoice",
            "res_model": "university.fee",
            "view_mode": "form",
            "target": "current",
        }

    def _open_action(self, res_model):
        return {
            "type": "ir.actions.act_window",
            "name": self.env[res_model]._description,
            "res_model": res_model,
            "view_mode": "list,form",
            "target": "current",
        }

    def action_open_semesters(self):
        return self._open_action("university.semester")

    def action_open_enrollment_history(self):
        return self._open_action("university.enrollment")

    def action_open_enrollment_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Bulk Enroll Students",
            "res_model": "university.bulk.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def _coming_soon_notification(self, title):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": "This feature is currently under development.",
                "type": "warning",
                "sticky": False,
            }
        }

    def action_open_academic_records(self):
        return self._coming_soon_notification("Academic Records")

    def action_open_teacher_assignments(self):
        return self._coming_soon_notification("Teacher Assignments")

    def action_open_scholarships(self):
        return self._coming_soon_notification("Scholarships")
