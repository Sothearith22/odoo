from odoo import api, fields, models

class UniversityCurriculum(models.Model):
    _name = "university.curriculum"
    _description = "University Curriculum"
    _order = "name"

    name = fields.Char(string="Curriculum Name", compute="_compute_name", store=True, readonly=False, required=True)
    program_id = fields.Many2one('university.program', string='Program', required=True)
    session_id = fields.Many2one('university.academic.year', string='Session', required=True)
    active = fields.Boolean(string="Active", default=True)
    line_ids = fields.One2many('university.curriculum.line', 'curriculum_id', string='Curriculum Lines')

    @api.depends('program_id', 'session_id')
    def _compute_name(self):
        for rec in self:
            if rec.program_id and rec.session_id and not rec.name:
                rec.name = f"{rec.program_id.name} - {rec.session_id.name}"


class UniversityCurriculumLine(models.Model):
    _name = "university.curriculum.line"
    _description = "Curriculum Line"
    _order = "year_level, semester, id"

    curriculum_id = fields.Many2one('university.curriculum', string='Curriculum', required=True, ondelete='cascade')
    subject_id = fields.Many2one('university.subject', string='Subject', required=True)
    
    year_level = fields.Selection([
        ('1', 'Year 1'),
        ('2', 'Year 2'),
        ('3', 'Year 3'),
        ('4', 'Year 4'),
        ('5', 'Year 5'),
        ('6', 'Year 6'),
    ], string="Year Level", required=True, default='1')

    semester = fields.Selection([
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
    ], string="Semester", required=True, default='1')

    credits = fields.Integer(string="Credits", related="subject_id.credits", store=True, readonly=False)
    required = fields.Boolean(string="Required", default=True)

    _sql_constraints = [
        (
            'unique_curriculum_subject_year_semester',
            'unique(curriculum_id, subject_id, year_level, semester)',
            'This subject already exists in this curriculum for this year and semester.'
        )
    ]
