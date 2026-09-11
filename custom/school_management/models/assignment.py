from odoo import api, fields, models
from odoo.exceptions import ValidationError

class UniversityAssignment(models.Model):
    _name = "university.assignment"
    _description = "Assignment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Assignment Name", required=True, tracking=True)
    teacher_id = fields.Many2one(
        "university.teacher", 
        string="Prepared By", 
        required=True, 
        default=lambda self: self._default_teacher()
    )
    subject_id = fields.Many2one("university.subject", string="Subject", required=True)
    section_id = fields.Many2one("university.class.section", string="Grade/Section", required=True)
    assignment_type = fields.Selection(
        [("class", "Class Assignment"), ("student", "Student Assignment")],
        string="Assignment Type",
        required=True,
        default="class"
    )
    description = fields.Html(string="Description")
    due_date = fields.Date(string="Due Date")
    category_id = fields.Many2one(
        "university.assessment.category",
        string="Assessment Category",
        domain="[('active', '=', True)]",
    )
    max_score = fields.Float(string="Max Score", default=100.0)
    submission_ids = fields.One2many(
        "university.assignment.submission",
        "assignment_id",
        string="Submissions",
    )
    submission_count = fields.Integer(
        string="Submission Count",
        compute="_compute_submission_count",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved")], 
        string="Status", 
        default="draft", 
        tracking=True
    )
    
    student_id = fields.Many2one(
        "university.student", 
        string="Student", 
        help="Specific student if this is a Student Assignment"
    )

    def _default_teacher(self):
        teacher = self.env["university.teacher"].search([("user_id", "=", self.env.uid)], limit=1)
        return teacher.id if teacher else False

    @api.depends("submission_ids")
    def _compute_submission_count(self):
        for assignment in self:
            assignment.submission_count = len(assignment.submission_ids)

    def action_approve(self):
        self.write({"state": "approved"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_view_submissions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Assignment Submissions",
            "res_model": "university.assignment.submission",
            "view_mode": "list,form",
            "domain": [("assignment_id", "=", self.id)],
            "context": {
                "default_assignment_id": self.id,
                "default_section_id": self.section_id.id,
                "default_subject_id": self.subject_id.id,
                "default_teacher_id": self.teacher_id.id,
                "default_category_id": self.category_id.id,
                "default_max_score": self.max_score,
            },
        }

    @api.constrains("max_score")
    def _check_max_score(self):
        for assignment in self:
            if assignment.max_score <= 0:
                raise ValidationError("Assignment maximum score must be greater than zero.")


class UniversityAssignmentSubmission(models.Model):
    _name = "university.assignment.submission"
    _description = "Assignment Submission"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submitted_on desc, id desc"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    assignment_id = fields.Many2one(
        "university.assignment",
        string="Assignment",
        required=True,
        ondelete="cascade",
        domain="[('state', '=', 'approved')]",
    )
    student_id = fields.Many2one(
        "university.student",
        string="Student",
        required=True,
        default=lambda self: self._default_student(),
    )
    section_id = fields.Many2one(
        "university.class.section",
        string="Class Section",
        related="assignment_id.section_id",
        store=True,
        readonly=True,
    )
    subject_id = fields.Many2one(
        "university.subject",
        string="Subject",
        related="assignment_id.subject_id",
        store=True,
        readonly=True,
    )
    teacher_id = fields.Many2one(
        "university.teacher",
        string="Teacher",
        related="assignment_id.teacher_id",
        store=True,
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        "university.academic.year",
        string="Academic Year",
        related="section_id.semester_id.academic_year_id",
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        "university.semester",
        string="Semester",
        related="section_id.semester_id",
        store=True,
        readonly=True,
    )
    category_id = fields.Many2one(
        "university.assessment.category",
        string="Assessment Category",
        related="assignment_id.category_id",
        store=True,
        readonly=True,
    )
    submitted_on = fields.Datetime(string="Submitted On")
    answer_text = fields.Html(string="Submission Text")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "university_assignment_submission_attachment_rel",
        "submission_id",
        "attachment_id",
        string="Attachments",
    )
    score = fields.Float(string="Score")
    max_score = fields.Float(
        string="Max Score",
        related="assignment_id.max_score",
        store=True,
        readonly=True,
    )
    feedback = fields.Html(string="Teacher Feedback")
    assessment_result_id = fields.Many2one(
        "university.assessment.result",
        string="Assessment Result",
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("evaluated", "Evaluated"),
            ("returned", "Returned"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    def _default_student(self):
        student = self.env["university.student"].search([("user_id", "=", self.env.uid)], limit=1)
        return student.id if student else False

    @api.depends("assignment_id.name", "student_id.name")
    def _compute_name(self):
        for submission in self:
            if submission.assignment_id and submission.student_id:
                submission.name = f"{submission.assignment_id.name} - {submission.student_id.name}"
            else:
                submission.name = "Assignment Submission"

    @api.constrains("student_id", "assignment_id")
    def _check_student_enrolled(self):
        for submission in self:
            if not submission.student_id or not submission.section_id:
                continue
            enrolled = self.env["university.enrollment"].search_count(
                [
                    ("student_id", "=", submission.student_id.id),
                    ("section_id", "=", submission.section_id.id),
                    ("status", "=", "enrolled"),
                ]
            )
            if not enrolled:
                raise ValidationError("Only enrolled students can submit work for this assignment.")

    @api.constrains("score", "max_score")
    def _check_score(self):
        for submission in self.filtered(lambda item: item.state == "evaluated"):
            if submission.score < 0 or submission.score > submission.max_score:
                raise ValidationError("Submission score must be between 0 and the assignment maximum score.")

    def action_submit(self):
        for submission in self:
            if not submission.answer_text and not submission.attachment_ids:
                raise ValidationError("Add submission text or at least one attachment before submitting.")
            submission.write(
                {
                    "state": "submitted",
                    "submitted_on": fields.Datetime.now(),
                }
            )

    def action_evaluate(self):
        for submission in self:
            if not submission.category_id:
                raise ValidationError("Set an assessment category on the assignment before evaluation.")
            if submission.score < 0 or submission.score > submission.max_score:
                raise ValidationError("Submission score must be between 0 and the assignment maximum score.")
            vals = {
                "student_id": submission.student_id.id,
                "section_id": submission.section_id.id,
                "subject_id": submission.subject_id.id,
                "teacher_id": submission.teacher_id.id,
                "academic_year_id": submission.academic_year_id.id,
                "semester_id": submission.semester_id.id,
                "category_id": submission.category_id.id,
                "assignment_id": submission.assignment_id.id,
                "submission_id": submission.id,
                "score": submission.score,
                "max_score": submission.max_score,
                "state": "published",
            }
            if submission.assessment_result_id:
                submission.assessment_result_id.write(vals)
            else:
                submission.assessment_result_id = self.env["university.assessment.result"].create(vals)
            submission.state = "evaluated"

    def action_return(self):
        self.write({"state": "returned"})
