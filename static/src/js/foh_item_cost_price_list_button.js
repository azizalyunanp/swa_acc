/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

export class FohItemCostPriceListController extends ListController {
    setup() {
        super.setup();
    }

    async onClickCalculateFohItemCostPrice() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "az.foh.item.cost.price.wizard",
            name: "FOH Item Cost Price",
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

FohItemCostPriceListController.template = "swa_acc.FohItemCostPriceListView.Buttons";

export const fohItemCostPriceListView = {
    ...listView,
    Controller: FohItemCostPriceListController,
};

registry.category("views").add("foh_item_cost_price_list", fohItemCostPriceListView);
