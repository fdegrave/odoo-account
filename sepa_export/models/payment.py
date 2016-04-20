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

_logger = logging.getLogger(__name__)


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
