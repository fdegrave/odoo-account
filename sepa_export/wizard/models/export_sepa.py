# -*- coding: utf-8 -*-
##############################################################################
#
#    UNamur - University of Namur, Belgium
#    Copyright (C) UNamur <http://www.unamur.be>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import jinja2
import logging
import base64
from os import path
import time
import operator
from itertools import groupby
from lxml import etree
import StringIO
from openerp.addons.base.res.res_bank import sanitize_account_number
from openerp.tools.safe_eval import safe_eval as eval


from openerp import models, fields, exceptions, api
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class ExportSEPAWiz(models.TransientModel):
    """Wizard to export outbound payments (type 'account.payment') into a SEPA file

    The payments are those identified by the 'active_ids' key of the context; only the payments with a payment type
    "outbound" in state "posted" are exported. The generated file is added
    """
    _name = 'account.export_sepa_wiz'

    def _validate_file(self, xml_data):
        # validate the generated XML schema
        xsd_path = path.realpath(path.join(path.dirname(__file__), '..', '..', 'data', 'pain.001.001.03.xsd'))
        with open(xsd_path) as xsd_file:
            schema_root = etree.parse(xsd_file)
            schema = etree.XMLSchema(schema_root)
            xml_data = etree.parse(StringIO.StringIO(xml_data))
            if not(schema.validate(xml_data)):
                raise exceptions.ValidationError(_("The generated SEPA file contains errors:\n %s") %
                                                 '\n'.join([str(err) for err in schema.error_log]))

    def _get_sepa_id(self, payments):
        """Create the SEPA file main identifier

        The identifier is 35 characters maximum, but it is recommended to limit it to 30 characters. The default code
        is "[code of the journal]/[date in %Y%m%d format]/[sequential number per day and journal]"
        Precondition:
            The payments are all in state "posted" and on the same journal
        """
        prefix = "%s/%s/" % (payments[0].journal_id.code, time.strftime('%Y%m%d'))
        existing = self.env['account.sepa_file'].search_count([('name', '=like', prefix + '%')])
        return "%s%03d" % (prefix, existing + 1)

    def _render_template(self, **kwargs):
        xml_path = path.realpath(path.join(path.dirname(__file__), '..', '..', 'report'))
        loader = jinja2.FileSystemLoader(xml_path)
        env = jinja2.Environment(loader=loader, autoescape=True)
        return env.get_template('sepa_template.xml').render(**kwargs)

    def _ensure_bank_bic(self, payments):
        """Ensure the partner bank account has a BIC code
        """
        for p in payments:
            for bnk in [p.partner_bank_id.bank_id, p.journal_id.bank_id]:
                if not(bnk.bic):
                    raise exceptions.ValidationError(_("The bank account %s (%s) has no BIC code") %
                                                     (bnk.acc_number, bnk.partner_id.name or _('No partner')))

    @api.multi
    def export_sepa(self):
        """Export payments (given in 'active_ids') to SEPA files

        The wizard exports one file per journal used for the payments. Each file is attached to a 'account.sepa_file'
        object from which the XML file is downloadable
        """
        def sort_key(pay): return pay.journal_id

        def format_comm(comm): return filter(str.isdigit, str(comm))

        def raise_error(msg): raise Exception(msg)
        pay_obj = self.env['account.payment']
        all_payments = pay_obj.browse(self._context['active_ids'])
        all_payments = all_payments.filtered(lambda p: p.payment_type == "outbound" and p.state == 'posted' and
                                             p.payment_method_code == "SEPA")
        if not(all_payments):
            raise exceptions.Warning(_("No SEPA payments to export"))
        self._ensure_bank_bic(all_payments)

        sepa_files = self.env['account.sepa_file']
        for _journal, payment_list in groupby(all_payments.sorted(key=sort_key), key=sort_key):
            payments = reduce(operator.add, payment_list, pay_obj.browse())
            amount_total = sum(payments.mapped(lambda p: p.amount))
            reference = self._get_sepa_id(payments)
            now = time.strftime('%Y-%m-%dT%H:%M:%S')
            company = payments[0].company_id
            company_vat = filter(str.isdigit, str(company.vat) or '')
            format_iban = sanitize_account_number
            pay_nbr = len(payments)
            kwargs = locals().copy()
            del kwargs['self']
            sepa_data = self._render_template(**kwargs).encode('utf-8')
            self._validate_file(sepa_data)
            sepa_files += sepa_files.create({'name': reference,
                                             'xml_file': base64.b64encode(sepa_data),
                                             'payment_ids': payments.mapped(lambda p: (4, p.id))})
            payments.write({'state': 'sent'})
        return {'context': self._context,
                'domain': "[('id', 'in', %s)]" % sepa_files.ids,
                'name': _('SEPA Files'),
                'res_model': 'account.sepa_file',
                'target': 'current',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'view_type': 'form'}
