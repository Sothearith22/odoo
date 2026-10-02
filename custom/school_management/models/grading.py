from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class UniversityGradeScale(models.Model):
    _name = "university.grade.scale"
    _description = "Grade Scale"
    _order = "name"

    name = fields.Char(string="Grade Scale", required=True)
    active = fields.Boolean(string="Active", default=True)
    line_ids = fields.One2many(
        "university.grade.scale.line",
        "scale_id",
        string="Grade Lines",
    )

    def get_grade_line(self, score):
        self.ensure_one()
        line = self.line_ids.filtered(
            lambda item: item.min_score <= score <= item.max_score
        )[:1]
        return line


class UniversityGradeScaleLine(models.Model):
    _name = "university.grade.scale.line"
    _description = "Grade Scale Line"
    _order = "scale_id, min_score desc, id"

    scale_id = fields.Many2one(
        "university.grade.scale",
        string="Grade Scale",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Grade", required=True)
    min_score = fields.Float(string="Minimum Score", required=True)
    max_score = fields.Float(string="Maximum Score", required=True, default=100.0)
    grade_point = fields.Float(string="Grade Point", required=True)
    is_passing = fields.Boolean(string="Passing Grade", default=True)

    @api.constrains("min_score", "max_score", "grade_point")
    def _check_grade_line_values(self):
        for line in self:
            if line.min_score > line.max_score:
                raise ValidationError("Minimum score cannot exceed maximum score.")
            if line.min_score < 0 or line.max_score > 100:
                raise ValidationError("Grade scale scores must be between 0 and 100.")
            if line.grade_point < 0:
                raise ValidationError("Grade points cannot be negative.")


class UniversityAssessmentCategory(models.Model):
    _name = "university.assessment.category"
    _description = "Assessment Category"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Category", required=True)
    code = fields.Char(string="Code", required=True)
    weight = fields.Float(
        string="Weight (%)",
        default=10.0,
        help="Percent contribution to the final subject score.",
    )
    active = fields.Boolean(string="Active", default=True)

    @api.constrains("weight")
    def _check_weight(self):
        for category in self:
            if category.weight <= 0 or category.weight > 100:
                raise ValidationError("Assessment category weight must be above 0 and no more than 100.")


class UniversityAssessmentResult(models.Model):
    _name = "university.assessment.result"
    _description = "Assessment Result"
    _order = "date desc, id desc"

    student_id = fields.Many2one("university.student", string="Student", required=True)
    program_id = fields.Many2one(
        "university.program",
        string="Major / Program",
        related="student_id.program_id",
        store=True,
        readonly=True,
    )
    section_id = fields.Many2one("university.class.section", string="Class Section")
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    teacher_id = fields.Many2one("university.teacher", string="Teacher")
    academic_year_id = fields.Many2one("university.academic.year", string="Academic Year", required=True)
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        required=True,
        domain="[('academic_year_id', '=', academic_year_id)]",
    )
    category_id = fields.Many2one(
        "university.assessment.category",
        string="Assessment Category",
        required=True,
        domain="[('active', '=', True)]",
    )
    assignment_id = fields.Many2one("university.assignment", string="Assignment")
    submission_id = fields.Many2one("university.assignment.submission", string="Submission")
    exam_id = fields.Many2one("university.exam", string="Examination", ondelete="set null")
    date = fields.Date(string="Assessment Date", default=fields.Date.context_today)
    score = fields.Float(string="Score", required=True)
    max_score = fields.Float(string="Max Score", default=100.0, required=True)
    percentage = fields.Float(string="Percentage", compute="_compute_scores", store=True)
    weighted_score = fields.Float(string="Weighted Score", compute="_compute_scores", store=True)
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        string="Status",
        default="draft",
    )

    @api.depends("score", "max_score", "category_id.weight")
    def _compute_scores(self):
        for result in self:
            if result.max_score:
                result.percentage = result.score / result.max_score * 100.0
                result.weighted_score = result.percentage * result.category_id.weight / 100.0
            else:
                result.percentage = 0.0
                result.weighted_score = 0.0

    @api.constrains("score", "max_score")
    def _check_score(self):
        for result in self:
            if result.max_score <= 0:
                raise ValidationError("Maximum score must be greater than zero.")
            if result.score < 0 or result.score > result.max_score:
                raise ValidationError("Score must be between 0 and the maximum score.")

    @api.constrains("semester_id", "academic_year_id")
    def _check_period(self):
        for result in self:
            if result.semester_id.academic_year_id != result.academic_year_id:
                raise ValidationError("The semester must belong to the selected academic year.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("allow_closed_year_write"):
            for vals in vals_list:
                year_id = vals.get("academic_year_id")
                if not year_id and vals.get("semester_id"):
                    semester = self.env["university.semester"].browse(vals.get("semester_id")).exists()
                    year_id = semester.academic_year_id.id if semester else False
                if year_id:
                    year = self.env["university.academic.year"].browse(year_id).exists()
                    if year and year.state in ("closed", "archived"):
                        raise UserError("Grades cannot be created for a closed or archived academic year.")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("allow_closed_year_write"):
            if any(res.academic_year_id.state in ("closed", "archived") for res in self):
                raise UserError("Grades of a closed or archived academic year cannot be modified.")
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("allow_closed_year_write"):
            if any(res.academic_year_id.state in ("closed", "archived") for res in self):
                raise UserError("Grades of a closed or archived academic year cannot be deleted.")
        return super().unlink()

    def action_publish(self):
        self.write({"state": "published"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})


class UniversityReportCard(models.Model):
    _name = "university.report.card"
    _description = "Report Card"
    _order = "academic_year_id desc, semester_id desc, id desc"

    name = fields.Char(
        string="Report Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: "New",
    )
    student_id = fields.Many2one("university.student", string="Student", required=True)
    program_id = fields.Many2one("university.program", string="Major / Program", related="student_id.program_id", store=True)
    academic_year_id = fields.Many2one("university.academic.year", string="Academic Year", required=True)
    semester_id = fields.Many2one("university.semester", string="Semester", required=True)
    grade_scale_id = fields.Many2one("university.grade.scale", string="Grade Scale", required=True)
    line_ids = fields.One2many("university.report.card.line", "report_card_id", string="Subjects")
    gpa = fields.Float(string="GPA", compute="_compute_gpa", store=True)
    total_credits = fields.Integer(string="Total Credits", compute="_compute_gpa", store=True)
    passed_credits = fields.Integer(string="Passed Credits", compute="_compute_gpa", store=True)
    academic_standing = fields.Selection(
        [
            ("dean_list", "Dean's List"),
            ("good", "Good Standing"),
            ("probation", "Academic Probation"),
        ],
        string="Academic Standing",
        compute="_compute_gpa",
        store=True,
    )
    evaluation_status = fields.Selection(
        [
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
        ],
        string="Status Overview",
        compute="_compute_evaluation_status",
        store=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("generated", "Generated"), ("approved", "Approved")],
        string="Status",
        default="draft",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("allow_closed_year_write"):
            for vals in vals_list:
                year_id = vals.get("academic_year_id")
                if not year_id and vals.get("semester_id"):
                    semester = self.env["university.semester"].browse(vals.get("semester_id")).exists()
                    year_id = semester.academic_year_id.id if semester else False
                if year_id:
                    year = self.env["university.academic.year"].browse(year_id).exists()
                    if year and year.state in ("closed", "archived"):
                        raise UserError("Report cards cannot be created for a closed or archived academic year.")
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("university.report.card") or "New"
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("allow_closed_year_write"):
            if any(card.academic_year_id.state in ("closed", "archived") for card in self):
                raise UserError("Report cards of a closed or archived academic year cannot be modified.")
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("allow_closed_year_write"):
            if any(card.academic_year_id.state in ("closed", "archived") for card in self):
                raise UserError("Report cards of a closed or archived academic year cannot be deleted.")
        return super().unlink()

    @api.depends("line_ids.credits", "line_ids.grade_point", "line_ids.is_passing")
    def _compute_gpa(self):
        for card in self:
            credits = sum(card.line_ids.mapped("credits"))
            passed = sum(line.credits for line in card.line_ids if line.is_passing)
            quality = sum(line.credits * line.grade_point for line in card.line_ids)
            card.total_credits = credits
            card.passed_credits = passed
            card.gpa = round(quality / credits, 2) if credits else 0.0

            if not card.line_ids:
                card.academic_standing = "good"
            elif card.gpa >= 3.5:
                card.academic_standing = "dean_list"
            elif card.gpa >= 2.0:
                card.academic_standing = "good"
            else:
                card.academic_standing = "probation"

    @api.depends("line_ids.evaluation_status")
    def _compute_evaluation_status(self):
        for card in self:
            if not card.line_ids or any(line.evaluation_status == "in_progress" for line in card.line_ids):
                card.evaluation_status = "in_progress"
            else:
                card.evaluation_status = "completed"

    def action_generate_lines(self):
        for card in self:
            # 1. Identify enrolled subjects for this student in the target semester
            enrollments = self.env["university.enrollment"].search([
                ("student_id", "=", card.student_id.id),
                ("semester_id", "=", card.semester_id.id),
                ("status", "in", ["enrolled", "completed"]),
            ])

            subjects = self.env["university.subject"]
            for enroll in enrollments:
                if enroll.section_id:
                    if enroll.section_id.subject_id:
                        subjects |= enroll.section_id.subject_id
                    slots = self.env["university.timetable.slot"].search([
                        ("section_id", "=", enroll.section_id.id),
                    ])
                    subjects |= slots.mapped("subject_id")
                if enroll.subject_id:
                    subjects |= enroll.subject_id

            published_results = self.env["university.assessment.result"].search([
                ("student_id", "=", card.student_id.id),
                ("academic_year_id", "=", card.academic_year_id.id),
                ("semester_id", "=", card.semester_id.id),
                ("state", "=", "published"),
            ])
            subjects |= published_results.mapped("subject_id")

            lines = [(5, 0, 0)]
            for subject in subjects:
                # A. Attendance Calculation (Grading_GPA_Policy.md §3.3)
                subject_sections = enrollments.mapped("section_id").filtered(
                    lambda s: s.subject_id == subject or subject in self.env["university.timetable.slot"].search([("section_id", "=", s.id)]).mapped("subject_id")
                )
                att_domain = [("student_id", "=", card.student_id.id)]
                if subject_sections:
                    att_domain.append(("section_id", "in", subject_sections.ids))

                att_records = self.env["university.attendance"].search(att_domain)
                actual_absents = len(att_records.filtered(lambda a: a.status == "absent"))
                total_permissions = len(att_records.filtered(lambda a: a.status == "permission"))
                total_lates = len(att_records.filtered(lambda a: a.status == "late"))

                effective_absences = actual_absents + (total_permissions // 2) + (total_lates // 4)
                attendance_score = max(0.0, 10.0 - (effective_absences * 1.0))

                # B. Component Results from published assessment results
                sub_results = published_results.filtered(lambda r: r.subject_id == subject)

                # Quiz (10%) - multi-quiz averaging
                quiz_res = sub_results.filtered(
                    lambda r: (r.category_id.code and "QUIZ" in r.category_id.code.upper())
                    or (r.category_id.name and "QUIZ" in r.category_id.name.upper())
                    or (r.exam_id and r.exam_id.exam_type == "quiz")
                )
                if quiz_res:
                    avg_quiz_pct = sum(r.percentage for r in quiz_res) / len(quiz_res)
                    quiz_score = round(avg_quiz_pct * 0.10, 2)
                else:
                    quiz_score = 0.0

                # Midterm Exam (20%)
                midterm_res = sub_results.filtered(
                    lambda r: (r.category_id.code and "MID" in r.category_id.code.upper())
                    or (r.category_id.name and "MID" in r.category_id.name.upper())
                    or (r.exam_id and r.exam_id.exam_type == "midterm")
                )
                if midterm_res:
                    avg_midterm_pct = sum(r.percentage for r in midterm_res) / len(midterm_res)
                    midterm_score = round(avg_midterm_pct * 0.20, 2)
                else:
                    midterm_score = 0.0

                # Assignments (10%) - multi-assignment averaging
                assign_res = sub_results.filtered(
                    lambda r: (r.category_id.code and "ASSIGN" in r.category_id.code.upper())
                    or (r.category_id.name and "ASSIGN" in r.category_id.name.upper())
                )
                if assign_res:
                    avg_assign_pct = sum(r.percentage for r in assign_res) / len(assign_res)
                    assignment_score = round(avg_assign_pct * 0.10, 2)
                else:
                    assignment_score = 0.0

                # Final Exam (50%)
                final_res = sub_results.filtered(
                    lambda r: (r.category_id.code and "FINAL" in r.category_id.code.upper())
                    or (r.category_id.name and "FINAL" in r.category_id.name.upper())
                    or (r.exam_id and r.exam_id.exam_type == "final")
                )
                if final_res:
                    avg_final_pct = sum(r.percentage for r in final_res) / len(final_res)
                    final_exam_score = round(avg_final_pct * 0.50, 2)
                else:
                    final_exam_score = 0.0

                # Other custom categories (if any)
                classified = quiz_res | midterm_res | assign_res | final_res
                other_res = sub_results - classified
                other_score = sum(r.weighted_score for r in other_res)

                # Total final score
                total_final_score = round(
                    attendance_score + quiz_score + midterm_score + assignment_score + final_exam_score + other_score,
                    2
                )
                total_final_score = min(100.0, max(0.0, total_final_score))

                grade_line = card.grade_scale_id.get_grade_line(total_final_score)
                is_completed = bool(final_res and midterm_res)

                lines.append(
                    (
                        0,
                        0,
                        {
                            "subject_id": subject.id,
                            "credits": subject.credits,
                            "attendance_score": attendance_score,
                            "quiz_score": quiz_score,
                            "midterm_score": midterm_score,
                            "assignment_score": assignment_score,
                            "final_exam_score": final_exam_score,
                            "final_score": total_final_score,
                            "grade": grade_line.name if grade_line else False,
                            "grade_point": grade_line.grade_point if grade_line else 0.0,
                            "is_passing": grade_line.is_passing if grade_line else False,
                            "evaluation_status": "completed" if is_completed else "in_progress",
                        },
                    )
                )

            card.write({"line_ids": lines, "state": "generated"})

    def action_approve(self):
        self.write({"state": "approved"})

    def action_print_report_card(self):
        return self.env.ref("school_management.action_report_university_report_card").report_action(self)


class UniversityReportCardLine(models.Model):
    _name = "university.report.card.line"
    _description = "Report Card Line"
    _order = "subject_id"

    report_card_id = fields.Many2one(
        "university.report.card",
        string="Report Card",
        required=True,
        ondelete="cascade",
    )
    student_id = fields.Many2one("university.student", related="report_card_id.student_id", store=True)
    academic_year_id = fields.Many2one("university.academic.year", related="report_card_id.academic_year_id", store=True)
    semester_id = fields.Many2one("university.semester", related="report_card_id.semester_id", store=True)
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    credits = fields.Integer(string="Credits")
    attendance_score = fields.Float(string="Attendance (10%)", digits=(5, 2))
    quiz_score = fields.Float(string="Quiz (10%)", digits=(5, 2))
    midterm_score = fields.Float(string="Midterm (20%)", digits=(5, 2))
    assignment_score = fields.Float(string="Assignment (10%)", digits=(5, 2))
    final_exam_score = fields.Float(string="Final Exam (50%)", digits=(5, 2))
    final_score = fields.Float(string="Total Score (%)", digits=(5, 2))
    grade = fields.Char(string="Grade")
    grade_point = fields.Float(string="Grade Point", digits=(3, 2))
    is_passing = fields.Boolean(string="Passing")
    evaluation_status = fields.Selection(
        [
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
        ],
        string="Status",
        default="completed",
    )


class UniversityTranscript(models.Model):
    _name = "university.transcript"
    _description = "Academic Transcript"
    _order = "id desc"

    name = fields.Char(
        string="Transcript Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: "New",
    )
    student_id = fields.Many2one("university.student", string="Student", required=True)
    program_id = fields.Many2one("university.program", string="Major / Program", related="student_id.program_id", store=True)
    line_ids = fields.One2many("university.transcript.line", "transcript_id", string="Transcript Lines")
    cumulative_gpa = fields.Float(string="Cumulative GPA", compute="_compute_cumulative_gpa", store=True)
    total_credits = fields.Integer(string="Total Credits", compute="_compute_cumulative_gpa", store=True)
    state = fields.Selection(
        [("draft", "Draft"), ("generated", "Generated"), ("approved", "Approved")],
        string="Status",
        default="draft",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("university.transcript") or "New"
        return super().create(vals_list)

    @api.depends("line_ids.credits", "line_ids.grade_point")
    def _compute_cumulative_gpa(self):
        for transcript in self:
            credits = sum(transcript.line_ids.mapped("credits"))
            quality = sum(line.credits * line.grade_point for line in transcript.line_ids)
            transcript.total_credits = credits
            transcript.cumulative_gpa = quality / credits if credits else 0.0

    def action_generate_lines(self):
        for transcript in self:
            cards = self.env["university.report.card"].search(
                [
                    ("student_id", "=", transcript.student_id.id),
                    ("state", "in", ["generated", "approved"]),
                ],
                order="academic_year_id, semester_id, id",
            )
            lines = [(5, 0, 0)]
            for card in cards:
                for card_line in card.line_ids:
                    lines.append(
                        (
                            0,
                            0,
                            {
                                "academic_year_id": card.academic_year_id.id,
                                "semester_id": card.semester_id.id,
                                "subject_id": card_line.subject_id.id,
                                "credits": card_line.credits,
                                "final_score": card_line.final_score,
                                "grade": card_line.grade,
                                "grade_point": card_line.grade_point,
                                "is_passing": card_line.is_passing,
                            },
                        )
                    )
            transcript.write({"line_ids": lines, "state": "generated"})

    def action_approve(self):
        self.write({"state": "approved"})

    def action_print_transcript(self):
        return self.env.ref("school_management.action_report_university_transcript").report_action(self)


class UniversityTranscriptLine(models.Model):
    _name = "university.transcript.line"
    _description = "Transcript Line"
    _order = "academic_year_id, semester_id, subject_id"

    transcript_id = fields.Many2one(
        "university.transcript",
        string="Transcript",
        required=True,
        ondelete="cascade",
    )
    academic_year_id = fields.Many2one("university.academic.year", string="Academic Year")
    semester_id = fields.Many2one("university.semester", string="Semester")
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    credits = fields.Integer(string="Credits")
    final_score = fields.Float(string="Final Score")
    grade = fields.Char(string="Grade")
    grade_point = fields.Float(string="Grade Point")
    is_passing = fields.Boolean(string="Passing")
