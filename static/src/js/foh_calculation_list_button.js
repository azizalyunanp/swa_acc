/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

export class FohCalculationListController extends ListController {
    setup() {
        super.setup();
    }

    async onClickCalculateFoh() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "az.foh.calculation.wizard",
            name: "Calculate FOH",
            view_mode: "form",
            view_type: "form",
            views: [[false, "form"]],
            target: "new",
            res_id: false,
        });
        // Reload list after wizard closes
        await this.model.load();
        this.render(true);
    }
}

FohCalculationListController.template = "swa_acc.FohCalculationListView.Buttons";

export const fohCalculationListView = {
    ...listView,
    Controller: FohCalculationListController,
};

registry.category("views").add("foh_calculation_list", fohCalculationListView);
