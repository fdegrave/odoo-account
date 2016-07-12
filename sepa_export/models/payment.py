# -*- encoding: utf-8 -*-
##############################################################################
#
#    UNamur - University of Namur, Belgium (www.unamur.be)
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
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp import models, fields, api, exceptions
from openerp.tools.translate import _
import logging
from itertools import groupby
from openerp.addons.base.res.res_bank import sanitize_account_number
import operator
import base64
import re
import time
import jinja2
from os import path
from lxml import etree
import StringIO

_logger = logging.getLogger(__name__)


class AccountRegisterPayments(models.TransientModel):
    _inherit = "account.register.payments"

    partner_bank_id = fields.Many2one('res.partner.bank', string="Partner Bank Account",
                                      domain="[('id','=',-1)")
    communication_type = fields.Selection([('none', 'Free Communication'), ('bba', 'BBA Structured Communication')],
                                          required=True, default='none', string="Communication Type")

    @api.onchange('partner_id')
    def _onchange_partner(self):
        return {'domain': {'partner_bank_id': [('partner_id', '=', self.partner_id.id or -1)]}}

    def get_payment_vals(self):
        res = super(AccountRegisterPayments, self).get_payment_vals()
        res['partner_bank_id'] = self.partner_bank_id.id
        res['communication_type'] = self.communication_type
        return res


class AccountPayment(models.Model):
    _inherit = "account.payment"

    sepa_file_id = fields.Many2one('account.sepa_file', string="SEPA File", readonly=True)
    partner_bank_id = fields.Many2one('res.partner.bank', string="Partner Bank Account",
                                      domain="[('id','=',-1)")
    communication_type = fields.Selection([('none', 'Free Communication'), ('bba', 'BBA Structured Communication')],
                                          required=True, default='none', string="Communication Type")

    @api.onchange('partner_id')
    def _onchange_partner(self):
        return {'domain': {'partner_bank_id': [('partner_id', '=', self.partner_id.id or -1)]}}

    def _validate_file(self, xml_data):
        # validate the generated XML schema
        xsd_path = path.realpath(path.join(path.dirname(__file__), '..', 'data', 'pain.001.001.03.xsd'))
        with open(xsd_path) as xsd_file:
            schema_root = etree.parse(xsd_file)
            schema = etree.XMLSchema(schema_root)
            xml_data = etree.parse(StringIO.StringIO(xml_data))
            if not(schema.validate(xml_data)):
                raise exceptions.ValidationError(_("The generated SEPA file contains errors:\n %s") %
                                                 '\n'.join([str(err) for err in schema.error_log]))

    def _render_template(self, **kwargs):
        xml_path = path.realpath(path.join(path.dirname(__file__), '..', 'templates'))
        loader = jinja2.FileSystemLoader(xml_path)
        env = jinja2.Environment(loader=loader, autoescape=True)
        return env.get_template('sepa_001.001.03.xml').render(**kwargs)

    def _ensure_bank_bic(self):
        """Ensure the partner bank account has a BIC code
        """
        for p in self:
            for bnk in [p.partner_bank_id.bank_id, p.journal_id.bank_id]:
                if not(bnk.bic):
                    raise exceptions.ValidationError(_("The bank account %s (%s) has no BIC code") %
                                                     (p.partner_bank_id.acc_number,
                                                      p.partner_id.name or _('No partner')))

    def _get_sepa_id(self):
        """Create the SEPA file main identifier

        The identifier is 35 characters maximum, but it is recommended to limit it to 30 characters. The default code
        is "[code of the journal]/[date in %Y%m%d format]/[sequential number per day and journal]"
        Precondition:
            The payments are all in state "posted" and on the same journal
        """
        prefix = "%s/%s/" % (self[0].journal_id.code, time.strftime('%Y%m%d'))
        existing = self.env['account.sepa_file'].search_count([('name', '=like', prefix + '%')])
        return "%s%03d" % (prefix, existing + 1)

    @api.multi
    def _create_sepa_files(self):
        """Export payments (given in 'active_ids') to SEPA files

        One file is created per journal used for the payments. Each file is attached to a 'account.sepa_file'
        object from which the XML file is downloadable
        """
        def sort_key(pay): return pay.journal_id

        def format_comm(comm): return filter(str.isdigit, str(comm))

        def raise_error(msg): raise Exception(msg)
        all_payments = self.filtered(lambda p: p.payment_type == "outbound" and p.state == 'posted' and
                                     p.payment_method_code == "SEPA")
        if not(all_payments):
            raise exceptions.Warning(_("No SEPA payments to export"))
        all_payments._ensure_bank_bic()

        sepa_files = self.env['account.sepa_file']
        for _journal, payment_list in groupby(all_payments.sorted(key=sort_key), key=sort_key):
            payments = reduce(operator.add, payment_list, self.browse())
            amount_total = sum(payments.mapped(lambda p: p.amount))
            reference = payments._get_sepa_id()
            company = payments[0].company_id
            company_vat = filter(str.isdigit, str(company.vat) or '')
            format_iban = sanitize_account_number
            pay_nbr = len(payments)
            now = time.strftime('%Y-%m-%dT%H:%M:%S')
            kwargs = locals().copy()
            del kwargs['self']
            sepa_data = self._render_template(**kwargs).encode('utf-8')
            self._validate_file(sepa_data)
            sepa_files += sepa_files.create({'name': reference,
                                             'xml_file': base64.b64encode(sepa_data),
                                             'payment_ids': payments.mapped(lambda p: (4, p.id))})
            payments.write({'state': 'sent'})
        return sepa_files

    @api.one
    @api.constrains('partner_bank_id', 'payment_method_id')
    def _partner_bank_required(self):
        """Ensure the partner bank account is set for payments using the SEPA method
        """
        for payment in self:
            if payment.payment_method_code == "SEPA" and not(payment.partner_bank_id):
                raise exceptions.ValidationError(_("The partner bank account is mandatory when using the SEPA method"))

    @api.one
    @api.constrains('company_id')
    def _vat_required(self):
        """Ensure the company has a fiscal number
        """
        for payment in self:
            if payment.payment_method_code == "SEPA" and not(payment.company_id.vat):
                raise exceptions.ValidationError(_("No fiscal number set on your company"))

    def _check_bba_comm(self):
        """Checks if the bba communication of `self` is well-formed"""
        def test_bba(val):
            supported_chars = '0-9+*/ '
            pattern = re.compile('[^' + supported_chars + ']')
            if pattern.findall(val or ''):
                return False
            bbacomm = re.sub('\D', '', val or '')
            if len(bbacomm) == 12:
                base = int(bbacomm[:10])
                mod = base % 97 or 97
                if mod == int(bbacomm[-2:]):
                    return True
            return False
        self.ensure_one()
        if not(test_bba(self.communication)):
            raise exceptions.ValidationError(_("BBA communication '%s' is invalid") % self.communication)

    @api.one
    @api.constrains('state', 'communication_type', 'payment_method_id')
    def _check_structured_comm(self):
        """Checks if the structured communication is well-formed when the payment is validated

        This method can check other communication types than 'bba' by simply extending the class with a
        '_check_[communication_type]_comm' method
        """
        payments = self.filtered(lambda p: p.state != 'draft')
        for payment in payments:
            getattr(self, "_check_%s_comm" % payment.communication_type, lambda *a: True)()


class Journal(models.Model):
    _inherit = "account.journal"

    @api.one
    @api.constrains('outbound_payment_method_ids', 'bank_id', 'bank_acc_number')
    def _journal_bank_required(self):
        """Ensure the journal is related to a bank account if it allows the SEPA payment method
        """
        for journal in self:
            if ('SEPA' in journal.outbound_payment_method_ids.mapped(lambda m: m.code) and
                    not(journal.bank_id and journal.bank_acc_number)):
                raise exceptions.ValidationError(_("A journal allowing the SEPA payment method must be associated to "
                                                   "a bank account number and a bank"))
