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
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Belgium - VAT Reporting',
    'version': '0.2a',
    'category': 'Localization/Account Charts',
    'description': """
    This module depends on account_report_template (https://github.com/unamur-dev/odoo-account) and provides a VAT
    reporting for Belgium.

    THIS IS AN ALPHA VERSION. All feedback is welcome. It should be all finished and tested by September.
    """,
    'author': 'University of Namur',
    'depends': [
        'l10n_be',
        'account_report_template',
    ],
    'data': [
        'data/vat_declaration.xml',
        'views/web_js.xml',
        'views/vat_reporting.xml',
    ],
    'qweb': [
        "static/src/xml/vat_export.xml",
    ],
    'demo': [],
    'installable': True
}
