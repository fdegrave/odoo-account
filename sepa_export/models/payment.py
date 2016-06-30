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
import re

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
