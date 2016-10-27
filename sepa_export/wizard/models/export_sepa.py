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

from odoo import models, api
from odoo.tools.translate import _
import logging

_logger = logging.getLogger(__name__)


class ExportSEPAWiz(models.TransientModel):
    """Wizard to export outbound payments (type 'account.payment') into a SEPA file

    The payments are those identified by the 'active_ids' key of the context; only the payments with a payment type
    "outbound" in state "posted" are exported. The generated file is added
    """
    _name = 'account.export_sepa_wiz'

    @api.multi
    def export_sepa(self):
        all_payments = self.env['account.payment'].browse(self._context['active_ids'])
        sepa_files = all_payments._create_sepa_files()
        return {'context': self._context,
                'domain': "[('id', 'in', %s)]" % sepa_files.ids,
                'name': _('SEPA Files'),
                'res_model': 'account.sepa_file',
                'target': 'current',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'view_type': 'form'}
