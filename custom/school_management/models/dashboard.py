import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _


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
    pending_admission_count = fields.Integer(string="Pending Admissions", compute="_compute_counts")
    attendance_rate = fields.Float(string="Attendance Rate", compute="_compute_counts")
    active_semester_name = fields.Char(string="Active Semester", compute="_compute_counts")

    teacher_count = fields.Integer(string="Teachers", compute="_compute_counts")
    faculty_count = fields.Integer(string="Faculties", compute="_compute_counts")
    department_count = fields.Integer(string="Departments", compute="_compute_counts")
    active_department_count = fields.Integer(string="Active Departments", compute="_compute_counts")
    program_count = fields.Integer(string="Programs", compute="_compute_counts")
    active_program_count = fields.Integer(string="Active Programs", compute="_compute_counts")
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
            rows = self.env[model]._read_group(domain or [], [], [f"{field}:sum"])
            return float(rows[0][0] or 0.0) if rows else 0.0
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

            rec.pending_admission_count = self._safe_count(
                "university.admission.application", [("state", "=", "submitted")]
            )
            rec.active_department_count = self._safe_count(
                "university.department", [("active", "=", True)]
            )
            rec.active_program_count = self._safe_count(
                "university.program", [("active", "=", True)]
            )
            rec.attendance_rate = self._get_attendance_rate()
            semester = self.env["university.semester"].browse()
            if self._can_read("university.semester"):
                try:
                    semester = self.env["university.semester"].search(
                        [("active", "=", True), ("academic_year_id.current", "=", True)],
                        order="date_start, id",
                        limit=1,
                    )
                except AccessError:
                    _logger.warning("Dashboard active semester is not readable for user %s", self.env.user.id)
            rec.active_semester_name = semester.display_name or _("No active semester")

    def _safe_read_group(self, model, domain, groupby, aggregates):
        if not self._can_read(model):
            return []
        try:
            return self.env[model]._read_group(domain or [], groupby, aggregates)
        except Exception:
            _logger.exception(
                "Dashboard grouped query failed for user %s on %s",
                self.env.user.id,
                model,
            )
            return []

    def _safe_search_read(self, model, domain, field_names, **kwargs):
        if not self._can_read(model):
            return []
        try:
            return self.env[model].search_read(domain or [], field_names, **kwargs)
        except Exception:
            _logger.exception(
                "Dashboard recent records query failed for user %s on %s",
                self.env.user.id,
                model,
            )
            return []

    def _period_domain(self, model, year_id=False, semester_id=False):
        model_fields = self.env[model]._fields
        domain = []
        if year_id and "academic_year_id" in model_fields:
            domain.append(("academic_year_id", "=", year_id))
        if semester_id and "semester_id" in model_fields:
            domain.append(("semester_id", "=", semester_id))
        return domain

    def _attendance_domain(self, year_id=False, semester_id=False):
        if semester_id:
            return [("section_id.semester_id", "=", semester_id)]
        if year_id:
            return [("section_id.semester_id.academic_year_id", "=", year_id)]
        return []

    def _get_attendance_rate(self, year_id=False, semester_id=False):
        rows = self._safe_read_group(
            "university.attendance",
            self._attendance_domain(year_id, semester_id),
            ["status"],
            ["__count"],
        )
        counts = {"present": 0, "absent": 0}
        for status, count in rows:
            if status in counts:
                counts[status] = count
        total = counts["present"] + counts["absent"]
        return round(counts["present"] * 100.0 / total, 1) if total else 0.0

    def _group_label(self, value):
        if hasattr(value, "display_name"):
            return value.display_name
        if isinstance(value, tuple):
            return value[1] if len(value) > 1 else value[0]
        return str(value or _("Unknown"))

    def _selected_period(self, year_id=False, semester_id=False):
        try:
            year_id = int(year_id or 0) or False
            semester_id = int(semester_id or 0) or False
            year_model = self.env["university.academic.year"]
            semester_model = self.env["university.semester"]

            year = year_model.browse(year_id).exists() if year_id else year_model.browse()
            semester = semester_model.browse(semester_id).exists() if semester_id else semester_model.browse()
            if semester and year and semester.academic_year_id != year:
                semester = semester_model.browse()
            if semester and not year:
                year = semester.academic_year_id
            if not year:
                year = year_model.search(
                    [("active", "=", True), ("current", "=", True)], limit=1
                )
            if not semester and year:
                semester = semester_model.search(
                    [("active", "=", True), ("academic_year_id", "=", year.id)],
                    order="date_start, id",
                    limit=1,
                )
            return year.id or False, semester.id or False
        except AccessError:
            _logger.warning("Dashboard period filters are not readable for user %s", self.env.user.id)
            return False, False

    @api.model
    def get_filter_options(self):
        years = self._safe_search_read(
            "university.academic.year",
            [("active", "=", True)],
            ["name", "current"],
            order="date_start desc, id desc",
        )
        semesters = self._safe_search_read(
            "university.semester",
            [("active", "=", True)],
            ["name", "academic_year_id", "semester_type"],
            order="date_start desc, id desc",
        )
        year_id, semester_id = self._selected_period()
        return {
            "academic_years": years,
            "semesters": semesters,
            "selected_year_id": year_id,
            "selected_semester_id": semester_id,
        }

    @api.model
    def get_dashboard_data(self, year_id=False, semester_id=False):
        year_id, semester_id = self._selected_period(year_id, semester_id)
        student_domain = self._period_domain("university.student", year_id, semester_id)
        enrollment_domain = self._period_domain("university.enrollment", year_id, semester_id)
        admission_domain = self._period_domain(
            "university.admission.application", year_id, semester_id
        )
        fee_domain = self._period_domain("university.fee", year_id, semester_id)
        payment_domain = self._period_domain("university.payment", year_id, semester_id)

        status_rows = self._safe_read_group(
            "university.student", student_domain, ["status"], ["__count"]
        )
        program_rows = self._safe_read_group(
            "university.student",
            student_domain + [("program_id", "!=", False)],
            ["program_id"],
            ["__count"],
        )
        enrollment_rows = self._safe_read_group(
            "university.enrollment",
            enrollment_domain,
            ["enrollment_date:month"],
            ["__count"],
        )
        fee_rows = self._safe_read_group(
            "university.payment",
            payment_domain + [("state", "=", "posted")],
            ["date:month"],
            ["amount:sum"],
        )

        attendance_rows = self._safe_read_group(
            "university.attendance",
            self._attendance_domain(year_id, semester_id),
            ["status"],
            ["__count"],
        )
        attendance = {"present": 0, "absent": 0}
        for status, count in attendance_rows:
            if status in attendance:
                attendance[status] = count
        total_attendance = attendance["present"] + attendance["absent"]
        attendance["rate"] = round(
            attendance["present"] * 100.0 / total_attendance, 1
        ) if total_attendance else 0.0

        total_paid = self._safe_sum(
            "university.payment", payment_domain + [("state", "=", "posted")], "amount"
        )
        total_unpaid = self._safe_sum(
            "university.fee",
            fee_domain + [("state", "=", "posted"), ("balance", ">", 0)],
            "balance",
        )
        semester_name = _("No active semester")
        if semester_id and self._can_read("university.semester"):
            semester_name = self.env["university.semester"].browse(semester_id).display_name or semester_name
        dashboard = {
            "student_count": self._safe_count("university.student", student_domain),
            "teacher_count": self._safe_count("university.teacher", [("active", "=", True)]),
            "program_count": self._safe_count("university.program"),
            "active_program_count": self._safe_count(
                "university.program", [("active", "=", True)]
            ),
            "department_count": self._safe_count("university.department"),
            "active_department_count": self._safe_count(
                "university.department", [("active", "=", True)]
            ),
            "faculty_count": self._safe_count("university.faculty"),
            "subject_count": self._safe_count("university.subject"),
            "section_count": self._safe_count("university.class.section"),
            "classroom_count": self._safe_count("university.classroom"),
            "active_student_count": self._safe_count(
                "university.student", student_domain + [("status", "=", "active")]
            ),
            "graduated_student_count": self._safe_count(
                "university.student", student_domain + [("status", "=", "graduated")]
            ),
            "suspended_student_count": self._safe_count(
                "university.student", student_domain + [("status", "=", "suspended")]
            ),
            "dropped_student_count": self._safe_count(
                "university.student", student_domain + [("status", "=", "dropped")]
            ),
            "fee_count": self._safe_count("university.fee", fee_domain),
            "payment_count": self._safe_count("university.payment", payment_domain),
            "pending_admission_count": self._safe_count(
                "university.admission.application", admission_domain + [("state", "=", "submitted")]
            ),
            "total_paid_fees": total_paid,
            "total_unpaid_fees": total_unpaid,
            "total_scholarships": 0.0,
            "attendance_rate": attendance["rate"],
            "active_semester_name": semester_name,
            "currency_symbol": self.env.company.currency_id.symbol or self.env.company.currency_id.name,
        }

        recent_admissions = self._safe_search_read(
            "university.admission.application",
            admission_domain,
            ["name", "applicant_name", "program_id", "application_date", "state"],
            limit=5,
            order="application_date desc, id desc",
        )
        recent_payments = self._safe_search_read(
            "university.payment",
            payment_domain + [("state", "=", "posted")],
            ["name", "amount", "date", "student_id", "payment_method", "reference", "state"],
            limit=5,
            order="date desc, id desc",
        )
        for payment in recent_payments:
            payment["student_name"] = (
                payment["student_id"][1] if payment.get("student_id") else _("Unknown")
            )
        pending_approvals = self._safe_search_read(
            "university.admission.application",
            admission_domain + [("state", "=", "submitted")],
            ["name", "applicant_name", "application_date", "state"],
            limit=5,
            order="application_date asc, id asc",
        )
        recent_activity = self._safe_search_read(
            "mail.activity",
            [],
            ["summary", "date_deadline", "user_id", "res_model", "res_id"],
            limit=8,
            order="date_deadline desc, id desc",
        )

        return {
            "dashboard": dashboard,
            "selected_year_id": year_id,
            "selected_semester_id": semester_id,
            "chart_data": {
                "program_distribution": {
                    "labels": [self._group_label(row[0]) for row in program_rows],
                    "data": [row[1] for row in program_rows],
                },
                "student_status": {
                    "labels": [self._group_label(row[0]).capitalize() for row in status_rows],
                    "data": [row[1] for row in status_rows],
                },
                "enrollment_trend": {
                    "labels": [self._group_label(row[0]) for row in enrollment_rows],
                    "data": [row[1] for row in enrollment_rows],
                },
                "monthly_fee_collection": {
                    "labels": [self._group_label(row[0]) for row in fee_rows],
                    "data": [float(row[1] or 0.0) for row in fee_rows],
                },
                "attendance_summary": attendance,
                "recent_admissions": recent_admissions,
                "recent_payments": recent_payments,
                "pending_approvals": pending_approvals,
                "recent_activity": recent_activity,
            },
        }

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
    [
        "name",
        "amount",
        "date",
        "student_id",
        "currency_id",
        "payment_method",
        "reference",
        "state",
    ],
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
