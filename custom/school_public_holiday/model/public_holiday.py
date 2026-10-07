import models
from odoo import fields


class PublicHoliday(models.Model):
    _name = 'public.holiday'
    _description = 'Public Holiday'
    _order = 'date desc'

    name = fields.Char(string='Name')
