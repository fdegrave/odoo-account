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

from odoo import models, fields, _
from odoo.tools.safe_eval import safe_eval
from docutils.nodes import row
from odoo.osv import expression

CSS = """
.account_report_table {
    white-space: nowrap;
    font-family: Roboto;
    font-size: 13px;
    color: #666666;
    line-height: 1em;
}

.account_report_table tr.account_report_row{
    color: inherit;
    font-weight: inherit;
}

.account_report_table tr.account_report_row_total{
    font-weight: bold;
}

.account_report_table tr.account_report_row1{
    border-width: 2px;
    border-bottom-style: solid;
}

.account_report_table tr.account_report_row2{
    border-width: 1px;
    border-top-style: solid;
    border-bottom-style: solid;
}

.account_report_table .account_report_row > td {
    padding: 3px 0px;
}

.account_report_table .account_report_row2 > td:first-child > span {
    margin-left: 25px;
}

.account_report_table .account_report_row3 > td:first-child > span {
    margin-left: 50px;
}

.account_report_table .account_report_row4 > td:first-child > span {
    margin-left: 75px;
}

td.account_report_cell_monetary {
    text-align: right;
}

.account_report_row_parent .account_report_value_cell{
    display: none;
}
"""

TITLE = """
<h2 style="margin-top: 0px;">%(name)s</h2>
<h4 class="text-muted">%(company)s</h4>
"""


def cols(debit_credit):
    return ['debit', 'credit', 'balance'] if debit_credit else ['balance']


class Row(object):

    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])

    def __getattr__(self, name):
        if name in ["credit", "debit", "balance"]:
            if getattr(self, '%s_formula' % name, None):
                expr = getattr(self, '%s_formula' % name)
                setattr(self, '%s_formula' % name, None)
                setattr(self, '%s_raw' % name, safe_eval(expr, self.env))
            return getattr(self, '%s_raw' % name, 0)
        return super(Row, self).__getattr__(name)

    def _to_cells(self):
        temp_line = self.template_line
        cells = [{"value": getattr(self, 'name', temp_line.name)}]
        for col in cols(self.debit_credit):
            cells.append({
                "value": float(getattr(self, col)),
                "style": temp_line.style,
                "css_class": 'account_report_value_cell account_report_cell_monetary',
                "options": "{'widget': 'monetary', 'display_currency': res_company.currency_id}"
                # xls_formula :to do, not that hard
            })
        css_class = self.css_class or ''
        # allow to 'force' the level for row containing the total
        css_class += ' account_report_row account_report_row%d' % getattr(self, 'level', temp_line.level)
        return {'css_class': css_class, 'code': getattr(self, 'code', False), 'cells': cells}


class ReportTemplate(models.Model):
    _name = "account_report_template.report_template"

    def _get_all_lines(self):
        """All the template lines in the hierarchy in a depth-first order"""
        def flatten(lines):
            res = self.env['account_report_template.report_template_line']
            for l in lines:
                res.append(l)
                res += flatten(l.children_ids)
            return res

        for temp in self:
            temp.all_line_ids = flatten(temp.line_ids)

    name = fields.Char('Name', size=128, required=True)
    show_debit_credit = fields.Boolean("Display Debit and Credit")
    line_ids = fields.One2many(comodel_name="account_report_template.report_template_line",
                               inverse_name="template_id", string="Details")  # lines
    all_line_ids = fields.One2many(comodel_name="account_report_template.report_template_line",
                                   compute=_get_all_lines, string="All Details")

    _order = 'name'

    def _to_table(self, domain):
        """We compile a template into a 'report_table.json_table' that we then use in QWeb
        """
        rows = []
        env = {}
        for row in self.line_ids._to_rows(domain, self.show_debit_credit):
            if row.code:
                env[row.code] = row
            row.env = env
            rows.append(row)

        company = self.env['res.company']._company_default_get()
        css_args = {
            'currency_symbol': company.currency_id.symbol,
            'currency_position': company.currency_id.position,
        }
        title = TITLE % {'name': self.name, 'company': company.name}
        return self.env['report_table.json_table'].create_from_literal(self.name, title=title, header=None,
                                                                       rows=[r._to_cells() for r in rows],
                                                                       css_class="account_report_table",
                                                                       css=CSS % css_args)


class ReportTemplateLine(models.Model):
    _name = "account_report_template.report_template_line"

    def _get_level(self):
        for line in self:
            if line.template_id:
                line.level = 1
            else:
                line.level = line.parent_id.level + 1

    template_id = fields.Many2one(comodel_name="account_report_template.report_template", string="Template",
                                  ondelete='cascade')
    name = fields.Char('Name', size=128, required=True)
    sequence = fields.Integer("Sequence")
    code = fields.Char('Code', size=16, index=True)
    style = fields.Char('CSS Style', size=128)
    css_class = fields.Char('CSS Class', size=128)
    domain = fields.Char("Journal Items Domain", help="A domain to apply on journal items")
    balance_formula = fields.Char("Formula to compute the balance")  # formula
    debit_formula = fields.Char("Formula to compute the debit")
    credit_formula = fields.Char("Formula to compute the credit")
    parent_id = fields.Many2one(comodel_name="account_report_template.report_template_line", string="Parent Line",
                                ondelete='cascade')
    children_ids = fields.One2many(comodel_name="account_report_template.report_template_line",
                                   inverse_name="parent_id", string="Sub-lines")
    level = fields.Integer("Depth in the Lines Hierarchy", compute=_get_level)

    _order = 'sequence'

    def _move_lines(self, domain):
        """Get the move lines associated to a template line, given the `domain` applied to the whole report"""
        if not self.domain:
            return self.env['account.move.line']
        dom = domain
        if self.domain:
            dom = expression.AND([domain or [], safe_eval(self.domain, {'ref': self.env.ref})])
        res = self.env['account.move.line'].search(dom or [])
        return res

    def _get_formula(self, col):
        """Get the formula
        We split on '_' if we have a comparaison between periods, meaning we could have credit_0, credit_1, etc.
        """
        colname = col.split('_')[0]
        return self['%s_formula' % colname]

    def _total_row(self, debit_credit):
        """Compute a additional child for a line containing the total, only if any formula field is set"""
        if self.children_ids and any(self['%s_formula' % f] for f in ['balance', 'credit', 'debit']):
            vals = {
                "template_line": self,
                'code': False,
                "name": _('Total %s') % self.name,
                "debit_credit": debit_credit,
                'css_class': self.css_class or '' + ' account_report_row_total',
                'level': self.level + 1
            }
            for col in cols(debit_credit):
                vals.update({"%s_formula" % col: self._get_formula(col), })
            return Row(**vals)

    def _to_rows(self, domain, debit_credit):
        """Compiles a template line into corresponding rows, given a recordset of move_lines
        """
        res = []
        for line in self:
            mlines = line._move_lines(domain)
            vals = {
                "template_line": line,
                "debit_credit": debit_credit,
                'code': line.code,
                'css_class': line.css_class or ''
            }
            if not(line.children_ids):
                for col in cols(debit_credit):
                    vals.update({
                        "%s_raw" % col: sum(ml[col] for ml in mlines),
                        "%s_formula" % col: line._get_formula(col),
                    })
            else:
                vals['css_class'] += ' account_report_row_parent'
            res.append(Row(**vals))
            res += line.children_ids._to_rows(domain, debit_credit)
            total_row = line._total_row(debit_credit)
            if total_row:
                res.append(total_row)
        return res
