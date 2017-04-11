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

from odoo.http import Controller, route, request
from odoo.addons.web.controllers.main import serialize_exception  # @UnresolvedImport


class XMLExportController(Controller):

    @route(['/export_xml/<model>/<docid>'], type='http', auth='user', website=True)
    @serialize_exception
    def export_xml(self, model, docid, token, **data):
        obj = request.env[model].browse(int(docid))
#         params = json.loads(obj.export_xml())
        filename, content = obj.export_xml()
        return request.make_response(content,
                                     headers=[('Content-Disposition', 'attachment; filename="%s"'
                                               % filename),
                                              ('Content-Type', 'text/xml')],
                                     cookies={'fileToken': token})
