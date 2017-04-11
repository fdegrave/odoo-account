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

from odoo import models, exceptions
from os import path
from lxml import etree
import StringIO
import jinja2

TAGS = ['00', '01', '02', '03',
        '44', '45', '46', '47', '48', '49',
        '54', '55', '56', '57', '59',
        '61', '62', '63', '64',
        '71', '72',
        '81', '82', '83', '84', '85', '86', '87', '88']


class PrintTemplateWiz(models.TransientModel):
    _inherit = "account_report_template.print_template_wiz"

    def print_templates(self):
        ctxt = {}
        if self.template_ids == self.env.ref('l10n_be_vat_reporting.declaration_template'):
            ctxt['export_be_vat_xml'] = True
        return super(PrintTemplateWiz, self.with_context(ctxt)).print_templates()

    def _validate_file(self, xml_data):
        """Validate the generated XML schema"""
        xsd_path = path.realpath(path.join(path.dirname(__file__), '..', 'data', 'vat_in.xsd'))
        with open(xsd_path) as xsd_file:
            schema_root = etree.parse(xsd_file)
            schema = etree.XMLSchema(schema_root)
            xml_data = etree.parse(StringIO.StringIO(xml_data))
            if not(schema.validate(xml_data)):
                raise exceptions.ValidationError(_("The generated VAT file contains errors:\n %s") %
                                                 '\n'.join([str(err) for err in schema.error_log]))

    def _render_template(self, **kwargs):
        xml_path = path.realpath(path.join(path.dirname(__file__), '..', 'data'))
        loader = jinja2.FileSystemLoader(xml_path)
        env = jinja2.Environment(loader=loader, autoescape=True)
        return env.get_template('xml_template.xml').render(**kwargs)

    def export_xml(self):
        def get_amount(tag):
            for row in self.table_ids[0].to_literal()['rows']:
                if row.get('code') == 'GRID%s' % tag:
                    return row['cells'][-1]['value']

        if len(self.template_ids) > 1:
            raise exceptions.UserError(_("The XML VAT declaration can be exported only for a single \"VAT "
                                         "Declaration\" report"))

        if self.template_ids == self.env.ref('l10n_be_vat_reporting.declaration_template'):
            if not self.quarter:
                raise exceptions.ValidationError(_("You can only export in XML for a complete quarter"))
            company = self.env['res.company']._company_default_get()
            partner = company.partner_id
            values = {
                "company": company,
                "partner": company.partner_id,
                "tags": TAGS,
                "company_vat": filter(str.isdigit, str(company.vat) or ''),
                'phone': filter(lambda c: c not in ' ./()', partner.phone or ''),
                "amount": get_amount,
                "quarter": self.quarter
            }
            res = self._render_template(**values)
            return 'XML_VAT_declaration.xml', res
