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
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class SEPAFile(models.Model):
    _name = 'account.sepa_file'

    def _get_filename(self):
        """The XML file name is a normalization of the SEPA file object name"""
        for sepafile in self:
            sepafile.xml_filename = "%s.xml" % (''.join(c if c.isalnum() else '_' for c in self.name))

    name = fields.Char(string='Reference', size=35, readonly=True, required=True)
    create_date = fields.Datetime(string='Creation Date', readonly=True, required=True)
    xml_file = fields.Binary("File", attachment=True, help="The SEPA file", readonly=True)
    xml_filename = fields.Char(string='File Name', readonly=True, compute="_get_filename")
    payment_ids = fields.One2many("account.payment", "sepa_file_id", "Activities", readonly=True)

    _order = "create_date desc"
