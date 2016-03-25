# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#
#    Copyright (c) 2012 Noviat nv/sa (www.noviat.be). All rights reserved.
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
import base64
import time

from openerp import api, models, fields, _
from openerp.exceptions import ValidationError
from openerp import tools

import logging

_logger = logging.getLogger(__name__)


def rmspaces(s):
    return " ".join(s.split())


class CodaImport(models.TransientModel):
    _name = 'account.coda.import'
    _description = 'Import CODA File'

    coda_data = fields.Binary(string='Bank Statement File', required=True,
                              help='Get you bank statements in electronic format from your bank and select them here.')

    def _parse_line(self, line, statements):
        if not line:
            return
        if line[0] == '0':
            statement = {}
            statements.append(statement)
        else:
            statement = statements[-1]
        try:
            meth = getattr(self, '_parse_line_%d' % line[0])
        except:
            ValidationError(_("CODA parsing error: lines starting with '%d' are not supported") % line[0])
        meth(line, statement)

    def _parse_line_0(self, line, statement):
        # Begin of a new Bank statement
        statement['version'] = line[127]
        if statement['version'] not in ['1', '2']:
            raise ValidationError(_('Error R001: CODA V%s statements are not supported, please '
                                    'contact your bank') % statement['version'])
        statement['globalisation_stack'] = []
        statement['lines'] = []
        statement['date'] = time.strftime(
            tools.DEFAULT_SERVER_DATE_FORMAT, time.strptime(rmspaces(line[5:11]), '%d%m%y'))
        statement['separateApplication'] = rmspaces(line[83:88])

    def _parse_line_1(self, line, statement):
        # Statement details
        if statement['version'] == '1':
            statement['acc_number'] = rmspaces(line[5:17])
            statement['currency'] = rmspaces(line[18:21])
        elif statement['version'] == '2':
            if line[1] == '0':  # Belgian bank account BBAN structure
                statement['acc_number'] = rmspaces(line[5:17])
                statement['currency'] = rmspaces(line[18:21])
            elif line[1] == '1':  # foreign bank account BBAN structure
                raise ValidationError(_('Error R1001: Foreign bank accounts with BBAN '
                                        'structure are not supported'))
            elif line[1] == '2':    # Belgian bank account IBAN structure
                statement['acc_number'] = rmspaces(line[5:21])
                statement['currency'] = rmspaces(line[39:42])
            elif line[1] == '3':    # foreign bank account IBAN structure
                raise ValidationError(_('Error R1002: Foreign bank accounts with IBAN structure '
                                        'are not supported'))
            else:  # Something else, not supported
                raise ValidationError(_('Error R1003: Unsupported bank account structure'))
        statement['journal_id'] = False
        statement['bank_account'] = False
        # Belgian Account Numbers are composed of 12 digits.
        # In Odoo, the user can fill the bank number in any format: With or without IBan code,
        # with or without spaces, with or without '-'
        # The two following sql requests handle those cases.
        if len(statement['acc_number']) >= 12:
            # If the Account Number is >= 12 digits, it is most likely a Belgian Account Number
            # (With or without IBAN).
            # The following request try to find the Account Number using a 'like' operator.
            # So, if the Account Number is stored with IBAN code, it can be found thanks to this.
            self._cr.execute("select id from res_partner_bank where "
                             "replace(replace(acc_number,' ',''),'-','') like %s",
                             ('%' + statement['acc_number'] + '%',))
        else:
            # This case is necessary to avoid cases like the Account Number in the CODA file is set to a single
            # or few digits,
            # and so a 'like' operator would return the first account number in the database which matches.
            self._cr.execute("select id from res_partner_bank where replace(replace(acc_number,' ',''),'-','') = %s",
                             (statement['acc_number'],))
        bank_ids = [r[0] for r in self._cr.fetchall()]
        # Filter bank accounts which are not allowed
        banks = self.env['res.partner.bank'].search([('id', 'in', bank_ids)])
        for bank_acc in banks:
            if (bank_acc.journal_id and
                ((bank_acc.journal_id.currency and
                  bank_acc.journal_id.currency.name == statement['currency']) or
                 (not bank_acc.journal_id.currency and
                  bank_acc.journal_id.company_id.currency_id.name == statement['currency']))):
                statement['journal_id'] = bank_acc.journal_id
                statement['bank_account'] = bank_acc
                break
        if not statement['bank_account']:
            raise ValidationError(_("Error R1004: No matching Bank Account (with Account Journal) "
                                    "found.\n\nPlease set-up a Bank Account with '%s' as "
                                    "Account Number and '%s' as Currency and an "
                                    "Account Journal.") % (statement['acc_number'],
                                                           statement['currency']))
        statement['description'] = rmspaces(line[90:125])
        statement['balance_start'] = float(rmspaces(line[43:58])) / 1000
        if line[42] == '1':  # 1 = Debit, the starting balance is negative
            statement['balance_start'] = - statement['balance_start']
        statement['balance_start_date'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT,
                                                        time.strptime(rmspaces(line[58:64]), '%d%m%y'))
        statement['accountHolder'] = rmspaces(line[64:90])
        statement['paperSeqNumber'] = rmspaces(line[2:5])
        statement['codaSeqNumber'] = rmspaces(line[125:128])

    def _parse_line_2(self, line, statement):
        if line[1] == '1':
            # New statement line
            statementLine = {}
            statementLine['ref'] = rmspaces(line[2:10])
            statementLine['ref_move'] = rmspaces(line[2:6])
            statementLine['ref_move_detail'] = rmspaces(line[6:10])
            statementLine['sequence'] = len(statement['lines']) + 1
            statementLine['transactionRef'] = rmspaces(line[10:31])
            statementLine['debit'] = line[31]  # 0 = Credit, 1 = Debit
            statementLine['amount'] = float(rmspaces(line[32:47])) / 1000
            if statementLine['debit'] == '1':
                statementLine['amount'] = - statementLine['amount']
            statementLine['transactionDate'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT,
                                                             time.strptime(rmspaces(line[47:53]), '%d%m%y'))
            statementLine['transaction_family'] = rmspaces(line[54:56])
            statementLine['transaction_code'] = rmspaces(line[56:58])
            statementLine['transaction_category'] = rmspaces(line[58:61])
            if line[61] == '1':
                # Structured communication
                statementLine['communication_struct'] = True
                statementLine['communication_type'] = line[62:65]
                statementLine['communication'] = (
                    '+++' + line[65:68] + '/' + line[68:72] + '/' + line[72:77] + '+++')
            else:
                # Non-structured communication
                statementLine['communication_struct'] = False
                statementLine['communication'] = rmspaces(line[62:115])
            statementLine['entryDate'] = time.strftime(
                tools.DEFAULT_SERVER_DATE_FORMAT, time.strptime(rmspaces(line[115:121]), '%d%m%y'))
            statementLine['type'] = 'normal'
            statementLine['globalisation'] = int(line[124])
            if statementLine['globalisation'] > 0:
                if statementLine['globalisation'] in statement['globalisation_stack']:
                    statement['globalisation_stack'].remove(statementLine['globalisation'])
                else:
                    statementLine['type'] = 'globalisation'
                    statement['globalisation_stack'].append(statementLine['globalisation'])
                self.global_comm[statementLine['ref_move']] = statementLine['communication']
            if not statementLine.get('communication'):
                statementLine['communication'] = self.global_comm.get(statementLine['ref_move'], '')
            statement['lines'].append(statementLine)
        elif line[1] == '2':
            if statement['lines'][-1]['ref'][0:4] != line[2:6]:
                raise ValidationError(_('CODA parsing error on movement data record 2.2, seq nr %s! '
                                        'Please report this issue via your Odoo support channel.') % line[2:10])
            statement['lines'][-1]['communication'] += rmspaces(line[10:63])
            statement['lines'][-1]['payment_reference'] = rmspaces(line[63:98])
            statement['lines'][-1]['counterparty_bic'] = rmspaces(line[98:109])
        elif line[1] == '3':
            if statement['lines'][-1]['ref'][0:4] != line[2:6]:
                raise ValidationError(_('CODA parsing error on movement data record 2.3, seq nr %s!'
                                        'Please report this issue via your Odoo support channel.') % line[2:10])
            if statement['version'] == '1':
                statement['lines'][-1]['counterpartyNumber'] = rmspaces(line[10:22])
                statement['lines'][-1]['counterpartyName'] = rmspaces(line[47:73])
                statement['lines'][-1]['counterpartyAddress'] = rmspaces(line[73:125])
                statement['lines'][-1]['counterpartyCurrency'] = ''
            else:
                if line[22] == ' ':
                    statement['lines'][-1]['counterpartyNumber'] = rmspaces(line[10:22])
                    statement['lines'][-1]['counterpartyCurrency'] = rmspaces(line[23:26])
                else:
                    statement['lines'][-1]['counterpartyNumber'] = rmspaces(line[10:44])
                    statement['lines'][-1]['counterpartyCurrency'] = rmspaces(line[44:47])
                statement['lines'][-1]['counterpartyName'] = rmspaces(line[47:82])
                statement['lines'][-1]['communication'] += rmspaces(line[82:125])
        else:
            # movement data record 2.x (x != 1,2,3)
            raise ValidationError(_('Movement data records of type 2.%s are not supported') % line[1])

    def _parse_line_3(self, line, statement):
        if line[1] == '1':
            infoLine = {}
            infoLine['entryDate'] = statement['lines'][-1]['entryDate']
            infoLine['type'] = 'information'
            infoLine['sequence'] = len(statement['lines']) + 1
            infoLine['ref'] = rmspaces(line[2:10])
            infoLine['transactionRef'] = rmspaces(line[10:31])
            infoLine['transaction_family'] = rmspaces(line[32:34])
            infoLine['transaction_code'] = rmspaces(line[34:36])
            infoLine['transaction_category'] = rmspaces(line[36:39])
            infoLine['communication'] = rmspaces(line[40:113])
            statement['lines'].append(infoLine)
        elif line[1] == '2':
            if infoLine['ref'] != rmspaces(line[2:10]):
                raise ValidationError(_('CODA parsing error on information data record 3.2, seq nr %s! '
                                        'Please report this issue via your Odoo support channel.') % line[2:10])
            statement['lines'][-1]['communication'] += rmspaces(line[10:100])
        elif line[1] == '3':
            if infoLine['ref'] != rmspaces(line[2:10]):
                raise ValidationError(_('CODA parsing error on information data record 3.3, seq nr %s! '
                                        'Please report this issue via your Odoo support channel.') % line[2:10])
            statement['lines'][-1]['communication'] += rmspaces(line[10:100])

    def _parse_line_4(self, line, statement):
        comm_line = {}
        comm_line['type'] = 'communication'
        comm_line['sequence'] = len(statement['lines']) + 1
        comm_line['ref'] = rmspaces(line[2:10])
        comm_line['communication'] = rmspaces(line[32:112])
        statement['lines'].append(comm_line)

    def _parse_line_8(self, line, statement):
        # new balance record
        statement['debit'] = line[41]
        statement['paperSeqNumber'] = rmspaces(line[1:4])
        statement['balance_end_real'] = float(rmspaces(line[42:57])) / 1000
        statement['date'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT,
                                          time.strptime(rmspaces(line[57:63]), '%d%m%y'))
        if statement['debit'] == '1':    # 1=Debit
            statement['balance_end_real'] = - statement['balance_end_real']

    def _parse_line_9(self, line, statement):
        statement['balanceMin'] = float(rmspaces(line[22:37])) / 1000
        statement['balancePlus'] = float(rmspaces(line[37:52])) / 1000
        if not statement.get('balance_end_real'):
            statement['balance_end_real'] = statement['balance_start'] + \
                statement['balancePlus'] - statement['balanceMin']

    @api.model
    def coda_parsing(self, batch=False, coda_file=None):
        self.ensure_one()
        coda_data = str(coda_file) if batch else self.coda_data
        recordlist = unicode(base64.decodestring(coda_data), 'windows-1252', 'strict').split('\n')
        statements = []
        self.global_comm = {}
        for line in recordlist:
            self.parse_line(line, statements)
        for i, statement in enumerate(statements):
            statement['coda_note'] = ''
            balance_start_check_date = ((len(statement['lines']) > 0 and statement['lines'][0]['entryDate']) or
                                        statement['date'])
            self._cr.execute('''SELECT balance_end_real
                                FROM account_bank_statement
                                WHERE journal_id = %s and date <= %s
                                ORDER BY date DESC,id DESC LIMIT 1''', (statement['journal_id'].id,
                                                                        balance_start_check_date))
            bal = self._cr.fetchone()
            balance_start_check = bal and bal[0]
            if balance_start_check is None:
                journal = statement['journal_id']
                if (journal.default_debit_account_id and
                        (journal.default_credit_account_id == journal.default_debit_account_id)):
                    balance_start_check = journal.default_debit_account_id.balance
                else:
                    raise ValidationError(_('Configuration Error in journal %s!\nPlease verify the '
                                            'Default Debit and Credit Account settings.') % journal.name)
            if balance_start_check != statement['balance_start']:
                statement['coda_note'] = (_("The CODA Statement %s Starting Balance (%.2f) does not correspond with "
                                            "the previous Closing Balance (%.2f) in journal %s!") %
                                           (statement['description'] + ' #' + statement['paperSeqNumber'],
                                            statement['balance_start'], balance_start_check,
                                            statement['journal_id'].name))
            if not(statement.get('date')):
                raise ValidationError(_(' No transactions or no period in coda file !'))
            res = {
                'name': statement['paperSeqNumber'],
                'date': statement['date'],
                'journal_id': statement['journal_id'].id,
                'period_id': statement['period_id'],
                'balance_start': statement['balance_start'],
                'balance_end_real': statement['balance_end_real'],
            }
            for line in statement['lines']:
                if line['type'] == 'information':
                    statement['coda_note'] = "\n".join([statement['coda_note'], line['type'].title(
                    ) + ' with Ref. ' + str(line['ref']), 'Date: ' + str(line['entryDate']), 'Communication: ' + line['communication'], ''])
                elif line['type'] == 'communication':
                    statement['coda_note'] = "\n".join([statement['coda_note'], line['type'].title(
                    ) + ' with Ref. ' + str(line['ref']), 'Ref: ', 'Communication: ' + line['communication'], ''])
                elif line['type'] == 'normal':
                    note = []
                    if 'counterpartyName' in line and line['counterpartyName'] != '':
                        note.append(_('Counter Party') + ': ' + line['counterpartyName'])
                    else:
                        line['counterpartyName'] = False
                    if 'counterpartyNumber' in line and line['counterpartyNumber'] != '':
                        try:
                            if int(line['counterpartyNumber']) == 0:
                                line['counterpartyNumber'] = False
                        except:
                            pass
                        if line['counterpartyNumber']:
                            note.append(_('Counter Party Account') + ': ' + line['counterpartyNumber'])
                    else:
                        line['counterpartyNumber'] = False

                    if 'counterpartyAddress' in line and line['counterpartyAddress'] != '':
                        note.append(_('Counter Party Address') + ': ' + line['counterpartyAddress'])
                    partner_id = None
                    structured_com = False
                    bank_account_id = False
                    if line['communication_struct'] and 'communication_type' in line and line['communication_type'] == '101':
                        structured_com = line['communication']
                    if 'counterpartyNumber' in line and line['counterpartyNumber']:
                        account = str(line['counterpartyNumber'])
                        domain = [('acc_number', '=', account)]
                        iban = account[0:2].isalpha()
                        if iban:
                            n = 4
                            space_separated_account = ' '.join(account[i:i + n] for i in range(0, len(account), n))
                            domain = ['|', ('acc_number', '=', space_separated_account)] + domain
                        ids = self.pool.get('res.partner.bank').search(cr, uid, domain)
                        if ids:
                            bank_account_id = ids[0]
                            bank_account = self.pool.get('res.partner.bank').browse(
                                cr, uid, bank_account_id, context=context)
                            line['counterpartyNumber'] = bank_account.acc_number
                            partner_id = bank_account.partner_id.id
                        else:
                            # create the bank account, not linked to any partner. The reconciliation will link the partner manually
                            # chosen at the bank statement final confirmation time.
                            try:
                                type_model, type_id = self.pool.get(
                                    'ir.model.data').get_object_reference(cr, uid, 'base', 'bank_normal')
                                type_id = self.pool.get('res.partner.bank.type').browse(
                                    cr, uid, type_id, context=context)
                                bank_code = type_id.code
                            except ValueError:
                                bank_code = 'bank'
                            bank_account_id = self.pool.get('res.partner.bank').create(
                                cr, uid, {'acc_number': str(line['counterpartyNumber']), 'state': bank_code}, context=context)
                    if line.get('communication', ''):
                        note.append(_('Communication') + ': ' + line['communication'])
                    data = {
                        'name': structured_com or (line.get('communication', '') != '' and line['communication'] or '/'),
                        'note': "\n".join(note),
                        'date': line['entryDate'],
                        'amount': line['amount'],
                        'partner_id': partner_id,
                        'partner_name': line['counterpartyName'],
                        'statement_id': statement['id'],
                        'ref': line['ref'],
                        'sequence': line['sequence'],
                        'bank_account_id': bank_account_id,
                    }
            if statement['coda_note'] != '':
                self.pool.get('account.bank.statement').write(
                    cr, uid, [statement['id']], {'coda_note': statement['coda_note']}, context=context)
        model, action_id = self.pool.get('ir.model.data').get_object_reference(
            cr, uid, 'account', 'action_bank_reconcile_bank_statements')
        action = self.pool[model].browse(cr, uid, action_id, context=context)
        statements_ids = [statement['id'] for statement in statements]
        return {
            'name': action.name,
            'tag': action.tag,
            'context': {'statement_ids': statements_ids},
            'type': 'ir.actions.client',
        }


class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'

    def _parse_file(self, data_file):
        """ Each module adding a file support must extends this method. It processes the file if it can, returns super otherwise, resulting in a chain of responsability.
            This method parses the given file and returns the data required by the bank statement import process, as specified below.
            rtype: triplet (if a value can't be retrieved, use None)
                - currency code: string (e.g: 'EUR')
                    The ISO 4217 currency code, case insensitive
                - account number: string (e.g: 'BE1234567890')
                    The number of the bank account which the statement belongs to
                - bank statements data: list of dict containing (optional items marked by o) :
                    - 'name': string (e.g: '000000123')
                    - 'date': date (e.g: 2013-06-26)
                    -o 'balance_start': float (e.g: 8368.56)
                    -o 'balance_end_real': float (e.g: 8888.88)
                    - 'transactions': list of dict containing :
                        - 'name': string (e.g: 'KBC-INVESTERINGSKREDIET 787-5562831-01')
                        - 'date': date
                        - 'amount': float
                        - 'unique_import_id': string
                        -o 'account_number': string
                            Will be used to find/create the res.partner.bank in odoo
                        -o 'note': string
                        -o 'partner_name': string
                        -o 'ref': string
        """
        return super(AccountBankStatementImport, self)._parse_file(data_file)
