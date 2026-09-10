from odoo import api, fields, models

class UniversityNoticeBoard(models.Model):
    _name = "university.notice.board"
    _description = "Notice Board"
    _order = "date desc"

    name = fields.Char(string="Title", required=True)
    date = fields.Date(string="Date", default=fields.Date.context_today)
    content = fields.Html(string="Notice Content")
    active = fields.Boolean(string="Active", default=True)
