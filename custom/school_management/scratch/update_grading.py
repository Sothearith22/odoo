with open('models/grading.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Honors grade point on UniversityGradeScaleLine
t1 = '    grade_point = fields.Float(string="Grade Point", required=True)\n    is_passing = fields.Boolean(string="Passing Grade", default=True)'
r1 = '    grade_point = fields.Float(string="Grade Point", required=True)\n    honors_grade_point = fields.Float(string="Honors Grade Point")\n    is_passing = fields.Boolean(string="Passing Grade", default=True)'
assert t1 in text, 't1 not found'
text = text.replace(t1, r1, 1)

# 2. company_id on UniversityReportCard
t2 = '    student_id = fields.Many2one("university.student", string="Student", required=True)'
r2 = '    company_id = fields.Many2one(\n        "res.company",\n        string="Company",\n        required=True,\n        default=lambda self: self.env.company,\n    )\n    student_id = fields.Many2one("university.student", string="Student", required=True)'
assert t2 in text, 't2 not found'
text = text.replace(t2, r2, 1)

# 3. _compute_gpa on UniversityReportCard
t3 = '''    @api.depends("line_ids.credits", "line_ids.grade_point", "line_ids.is_passing")
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
                card.academic_standing = "probation"'''

r3 = '''    @api.depends("line_ids.credits", "line_ids.grade_point", "line_ids.is_passing", "program_id.min_graduation_grade_id")
    def _compute_gpa(self):
        ICP = self.env["ir.config_parameter"].sudo()
        try:
            min_gpa = float(ICP.get_param("school_management.deans_list_min_gpa", 3.5))
        except (ValueError, TypeError):
            min_gpa = 3.5
        try:
            min_credits = float(ICP.get_param("school_management.deans_list_min_credits", 12))
        except (ValueError, TypeError):
            min_credits = 12.0

        for card in self:
            credits = sum(card.line_ids.mapped("credits"))
            min_grad = card.program_id.min_graduation_grade_id
            if min_grad:
                passed = sum(line.credits for line in card.line_ids if line.is_passing and line.grade_point >= min_grad.grade_point)
            else:
                passed = sum(line.credits for line in card.line_ids if line.is_passing)
            quality = sum(line.credits * line.grade_point for line in card.line_ids)
            card.total_credits = credits
            card.passed_credits = passed
            card.gpa = round(quality / credits, 2) if credits else 0.0

            if not card.line_ids:
                card.academic_standing = "good"
            elif card.gpa >= min_gpa and card.passed_credits >= min_credits:
                card.academic_standing = "dean_list"
            elif card.gpa >= 2.0:
                card.academic_standing = "good"
            else:
                card.academic_standing = "probation"'''

assert t3 in text, 't3 not found'
text = text.replace(t3, r3, 1)

# 4. company_id and academic_standing on UniversityTranscript
t4 = '''    cumulative_gpa = fields.Float(string="Cumulative GPA", compute="_compute_cumulative_gpa", store=True)
    total_credits = fields.Integer(string="Total Credits", compute="_compute_cumulative_gpa", store=True)
    state = fields.Selection('''

r4 = '''    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    academic_standing = fields.Selection(
        [
            ("dean_list", "Dean's List"),
            ("good", "Good Standing"),
            ("probation", "Academic Probation"),
        ],
        string="Academic Standing",
        compute="_compute_academic_standing",
        store=True,
    )
    cumulative_gpa = fields.Float(string="Cumulative GPA", compute="_compute_cumulative_gpa", store=True)
    total_credits = fields.Integer(string="Total Credits", compute="_compute_cumulative_gpa", store=True)
    state = fields.Selection('''

assert t4 in text, 't4 not found'
text = text.replace(t4, r4, 1)

# 5. _compute_academic_standing on UniversityTranscript
t5 = '''    @api.depends("line_ids.credits", "line_ids.grade_point")
    def _compute_cumulative_gpa(self):
        for transcript in self:
            credits = sum(transcript.line_ids.mapped("credits"))
            quality = sum(line.credits * line.grade_point for line in transcript.line_ids)
            transcript.total_credits = credits
            transcript.cumulative_gpa = quality / credits if credits else 0.0'''

r5 = '''    @api.depends("line_ids.credits", "line_ids.grade_point")
    def _compute_cumulative_gpa(self):
        for transcript in self:
            credits = sum(transcript.line_ids.mapped("credits"))
            quality = sum(line.credits * line.grade_point for line in transcript.line_ids)
            transcript.total_credits = credits
            transcript.cumulative_gpa = quality / credits if credits else 0.0

    @api.depends(
        "student_id.report_card_ids.academic_standing",
        "student_id.report_card_ids.state",
        "cumulative_gpa",
        "total_credits",
    )
    def _compute_academic_standing(self):
        ICP = self.env["ir.config_parameter"].sudo()
        try:
            min_gpa = float(ICP.get_param("school_management.deans_list_min_gpa", 3.5))
        except (ValueError, TypeError):
            min_gpa = 3.5
        try:
            min_credits = float(ICP.get_param("school_management.deans_list_min_credits", 12))
        except (ValueError, TypeError):
            min_credits = 12.0

        for transcript in self:
            latest_card = self.env["university.report.card"].search(
                [
                    ("student_id", "=", transcript.student_id.id),
                    ("state", "in", ["generated", "approved"]),
                ],
                order="academic_year_id desc, semester_id desc, id desc",
                limit=1,
            )
            if latest_card:
                transcript.academic_standing = latest_card.academic_standing
            else:
                if transcript.cumulative_gpa >= min_gpa and transcript.total_credits >= min_credits:
                    transcript.academic_standing = "dean_list"
                elif transcript.cumulative_gpa >= 2.0:
                    transcript.academic_standing = "good"
                else:
                    transcript.academic_standing = "probation"'''

assert t5 in text, 't5 not found'
text = text.replace(t5, r5, 1)

with open('models/grading.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print('Updated models/grading.py successfully')
