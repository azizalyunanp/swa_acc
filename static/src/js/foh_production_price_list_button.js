/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class FohProductionPriceListController extends ListController {
    setup() {
        super.setup()
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    /**
     * Calculate average product cost from selected az_foh_production_price records
     * and write results to az_foh_cost_price_fg.
     */
    async onClickCalculateAverageProduct() {
        const selectedRecords = this.model.root.selection;
        if (selectedRecords.length === 0) {
            this.notification.add(
                _t("Please select at least one record."),
                { type: "warning" }
            );
            return;
        }

        const recordIds = selectedRecords.map(record => record.resId);

        try {
            await this.orm.call(
                "az.foh.cost.price.fg",
                "calculate_average_from_production_price",
                [recordIds]
            );

            this.notification.add(
                _t("Average product cost calculated successfully."),
                { type: "success" }
            );

            await this.model.load();
            this.render(true);
        } catch (error) {
            this.notification.add(
                _t("Error during calculation: ") + (error.data?.message || error.message || ""),
                { type: "danger" }
            );
        }
    }
}

FohProductionPriceListController.template = "swa_acc.FohProductionPriceListView.Buttons";

export const fohProductionPriceListView = {
    ...listView,
    Controller: FohProductionPriceListController,
};

registry.category("views").add("foh_production_price_list", fohProductionPriceListView);
