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

from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta
from calendar import monthrange


class AccountTemplate(models.TransientModel):
    _name = "account_report_template.print_template_wiz"

    period = fields.Selection([('this_year', "This Fiscal Year"),
                               ('this_quarter', "This Quarter"),
                               ('this_month', "This Month"),
                               ('last_year', "Last Fiscal Year"),
                               ('last_quarter', "Last Quarter"),
                               ('last_month', "Last Month"),
                               ('custom', "Custom")], string="Date Range", required=True, default="this_year")
    from_date = fields.Date("From Date", required=True, default=fields.Date.today())
    to_date = fields.Date("To Date", required=True, default=fields.Date.today())
    quarter = fields.Integer("Quarter")
    month = fields.Integer("Month")
    template_ids = fields.Many2many(comodel_name='account_report_template.report_template',
                                    relation='account_report_template_wiz_rel',
                                    column1='wiz_id', column2='template_id', string="Templates to Print", required=True)
    table_ids = fields.Many2many(comodel_name='report_table.json_table',
                                 relation='account_report_wiz_json_table_rel',
                                 column1='wiz_id', column2='table_id', string="JSON Tables Generated")

    def _set_quarter(self):
        if not(self.quarter) or self.get_quarter_dates(day=self.from_date) != (self.from_date, self.to_date):
            self.quarter = 0

    def get_quarter_dates(self, last=False, day=False):
        if not day:
            day = date.today() - relativedelta(months=3) if last else date.today()
        else:
            day = fields.Date.from_string(day)
        quarter = 1 + (day.month - 1) // 3
        if self:
            self.quarter = quarter
        year = day.year
        first_month_of_quarter = 3 * quarter - 2
        last_month_of_quarter = 3 * quarter
        quarter_start = "%04d-%02d-%02d" % (year, first_month_of_quarter, 1)
        quarter_end = "%04d-%02d-%02d" % (year, last_month_of_quarter, monthrange(year, last_month_of_quarter)[1])
        return quarter_start, quarter_end

    def get_year_dates(self, last=False):
        company = self.env['res.company']._company_default_get()
        day = date.today() - relativedelta(years=1) if last else date.today()
        last_day = "%04d-%02d-%02d" % (day.year, company.fiscalyear_last_month, company.fiscalyear_last_day)
        last_date = fields.Date.from_string(last_day)
        first_date = last_date + relativedelta(days=1) - relativedelta(years=1)
        return fields.Date.to_string(first_date), last_day

    def _set_month(self):
        if not(self.month) or self.get_month_dates(day=fields.Date.from_string(self.from_date)) != (self.from_date, self.to_date):
            self.month = 0

    def get_month_dates(self, last=False, day=False):
        if not day:
            day = date.today() - relativedelta(months=1) if last else date.today()
        if self:
            self.month = day.month
        first_day = "%04d-%02d-%02d" % (day.year, day.month, 1)
        last_day = "%04d-%02d-%02d" % (day.year, day.month, monthrange(day.year, day.month)[1])
        return first_day, last_day

    @api.onchange('period')
    def _onchange_period(self):
        if self.period and self.period != 'custom':
            when, what = self.period.split('_')
            meth = getattr(self, 'get_%s_dates' % what)
            self.from_date, self.to_date = meth(last=when == 'last')

    @api.multi
    def print_templates(self):
        """Print the templates """
        self._onchange_period()
        self._set_quarter()
        self._set_month()
        dom = [('date', '>=', self.from_date), ('date', '<=', self.to_date)]
        self.table_ids = self.template_ids.mapped(lambda t: t._to_table(dom))
        res = self.env['report'].get_action(self, 'account_report_template.print_template')
        res['name'] = self.template_ids[0].name
        res['target'] = 'main'
        return res
