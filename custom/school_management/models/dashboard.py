from odoo import api
from odoo import api, fields, models


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

    def _compute_counts(self):
        for rec in self:
            rec.student_count = self.env["university.student"].search_count([])
            rec.active_student_count = self.env["university.student"].search_count([("status", "=", "active")])
            rec.suspended_student_count = self.env["university.student"].search_count([("status", "=", "suspended")])
            rec.graduated_student_count = self.env["university.student"].search_count([("status", "=", "graduated")])
            rec.dropped_student_count = self.env["university.student"].search_count([("status", "=", "dropped")])

            rec.teacher_count = self.env["university.teacher"].search_count([])
            rec.faculty_count = self.env["university.faculty"].search_count([])
            rec.department_count = self.env["university.department"].search_count([])
            rec.program_count = self.env["university.program"].search_count([])
            rec.subject_count = self.env["university.subject"].search_count([])
            rec.classroom_count = self.env["university.classroom"].search_count([])
            rec.section_count = self.env["university.class.section"].search_count([])
            rec.enrollment_count = self.env["university.enrollment"].search_count([])
            rec.fee_count = self.env["university.fee"].search_count([])
            rec.payment_count = self.env["university.payment"].search_count([])
            
            # Financials
            posted_fees = self.env["university.fee"].search([("state", "in", ("posted", "paid"))])
            rec.total_unpaid_fees = sum(posted_fees.mapped("balance"))
            
            posted_payments = self.env["university.payment"].search([("state", "=", "posted")])
            rec.total_paid_fees = sum(posted_payments.mapped("amount"))
            
            # Placeholder until phase 5 part 2
            rec.total_scholarships = 0.0

    @api.model
    def get_chart_data(self):
        # 1. Program Distribution (Bar Chart)
        self.env.cr.execute("""
            SELECT p.name, COUNT(s.id) 
            FROM university_student s
            JOIN university_program p ON s.program_id = p.id
            WHERE s.active = True
            GROUP BY p.name
            ORDER BY COUNT(s.id) DESC
            LIMIT 10
        """)
        program_data = self.env.cr.fetchall()

        # 2. Student Demographics (Doughnut Chart)
        self.env.cr.execute("""
            SELECT status, COUNT(id)
            FROM university_student
            GROUP BY status
        """)
        status_data = self.env.cr.fetchall()
        
        # 3. Recent Activity (Last 5 Payments)
        recent_payments = self.env["university.payment"].search_read(
            [("state", "=", "posted")],
            ["name", "amount", "date", "student_id", "currency_id"],
            limit=5,
            order="date desc, id desc"
        )
        
        # Resolve related fields for recent payments
        for p in recent_payments:
            if p.get("student_id"):
                p["student_name"] = p["student_id"][1]
            else:
                p["student_name"] = "Unknown"

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
            "name": "New Course Enrollment",
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
            "name": "Multiple Enrollments",
            "res_model": "university.enrollment.wizard",
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
