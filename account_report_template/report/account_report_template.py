# -*- coding: utf-8 -*-
##############################################################################
#
#    UNamur - University of Namur, Belgium
#    Copyright (C) UNamur <http://www.unamur.be>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import api, models


class ReportTable(models.AbstractModel):
    _name = 'report.account_report_template.print_template'

    @api.multi
    def render_html(self, docids, data=None):
        wiz_ids = docids or self._context.get('active_ids')
        wiz = self.env["account_report_template.print_template_wiz"].browse(wiz_ids)
        tables = wiz.mapped('table_ids')
        return self.env['report.report_table.report_json_table'].render_html(tables.ids)
