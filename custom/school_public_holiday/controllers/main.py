
from odoo import http
from odoo.http import request

class PublicHolidayController(http.Controller):

    @http.route('/holidays', type='http', auth='public', website=True)
    def holiday_list(self, **kw):
        holidays = request.env['public.holiday'].sudo().search([])
        return request.render('school_public_holiday.holiday_page', {'holidays': holidays})