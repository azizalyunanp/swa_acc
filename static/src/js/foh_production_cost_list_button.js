/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

export class FohProductionCostListController extends ListController {
    setup() {
        super.setup();
    }

    async onClickGenerateFohProductionCost() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "az.foh.generate.mrp.wizard",
            name: "Generate FOH Production Cost",
            view_mode: "form",
            view_type: "form",
            views: [[false, "form"]],
            target: "new",
            res_id: false,
        });
        await this.model.load();
        this.render(true);
    }
}

FohProductionCostListController.template = "swa_acc.FohProductionCostListView.Buttons";

export const fohProductionCostListView = {
    ...listView,
    Controller: FohProductionCostListController,
};

registry.category("views").add("foh_production_cost_list", fohProductionCostListView);
