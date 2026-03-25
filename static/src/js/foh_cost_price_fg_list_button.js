/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class FohCostPriceFgListController extends ListController {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
    }

    async onClickUpdateStandardPrice() {
        const selectedRecords = this.model.root.selection;
        if (selectedRecords.length === 0) {
            this.notification.add(
                _t("Please select at least one record."),
                { type: "warning" }
            );
            return;
        }

        // Show Yes/No confirmation before proceeding
        this.dialog.add(ConfirmationDialog, {
            title: _t("Update Standard Price"),
            body: _t(
                `Are you sure you want to update the standard price for ${selectedRecords.length} selected record(s)? This will overwrite the current product/lot standard price.`
            ),
            confirm: async () => {
                const recordIds = selectedRecords.map(record => record.resId);
                try {
                    await this.orm.call(
                        "az.foh.cost.price.fg",
                        "update_standard_price_batch",
                        [recordIds]
                    );
                    this.notification.add(
                        _t("Standard price updated successfully."),
                        { type: "success" }
                    );
                    await this.model.load();
                    this.render(true);
                } catch (error) {
                    this.notification.add(
                        _t("Error: ") + (error.data?.message || error.message || ""),
                        { type: "danger" }
                    );
                }
            },
            cancel: () => {},
        });
    }
}

FohCostPriceFgListController.template = "swa_acc.FohCostPriceFgListView.Buttons";

export const fohCostPriceFgListView = {
    ...listView,
    Controller: FohCostPriceFgListController,
};

registry.category("views").add("foh_cost_price_fg_list", fohCostPriceFgListView);
