odoo.define('l10n_be_vat_reporting.vat_export', function (require) {
    'use strict';
    
    var core = require('web.core');
    var QWeb = core.qweb;
    var ReportAction = require('report.client_action');
    var crash_manager = require('web.crash_manager');
    
    ReportAction.include({
        start: function () {
            var res = this._super.apply(this, arguments);
            var self = this;
            this.edit_mode_available = false;
            if (self.$buttons && self.context.export_be_vat_xml){
                self.$buttons.find('button.vat_report_xml_export').css({'display': 'inline-block'});
                self.$buttons.find('button.vat_report_xml_export').on('click', self.on_click_export_vat_xml);
            }
            return res;
        },

        on_click_export_vat_xml: function () {
            var view = this.getParent();
            $.blockUI();
            view.session.get_file({
                url: '/export_xml/' + this.context.active_model + '/' + this.context.active_id,
                data: {},
                complete: $.unblockUI,
                error: crash_manager.rpc_error.bind(crash_manager),
            });
        },
    });
});
