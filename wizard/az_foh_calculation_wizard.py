# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
import calendar


FOH_TYPES = [
    'electricity',
    'wage',
    'overtime',
    'others',
    'sparepart',
    'fuel',
    'depreciation',
    'work_order',
    'packing',
]

# Map FOH type → field suffix on az.foh.calculation
FOH_FIELD_MAP = {
    'electricity': 'electricity',
    'wage': 'wage',
    'overtime': 'overtime',
    'others': 'others',
    'sparepart': 'sparepart',
    'fuel': 'fuel',
    'depreciation': 'depreciation',
    'work_order': 'workorder',
    'packing': 'packing',
}


class AzFohCalculationWizard(models.TransientModel):
    _name = 'az.foh.calculation.wizard'
    _description = 'FOH Calculation Wizard'

    from_date = fields.Date(
        string='From Date',
        required=True,
    )
    to_date = fields.Date(
        string='To Date',
        required=True,
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Location',
        required=True,
        domain=[('usage', '=', 'internal')],
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    def calc_foh(self):
        """
        Fungsi utama wizard untuk menghitung Factory Overhead (FOH).

        Alur kerja:
        1. Validasi input tanggal
        2. Ambil data produksi (mrp.production) sesuai filter
        3. Hitung total qty per produk
        4. Ambil rasio bobot produk dari master az.item.foh.ratio
        5. Hitung prod_equ dan bobot proporsi tiap produk
        6. Ambil total biaya FOH dari jurnal akuntansi (account.move.line)
           berdasarkan mapping COA ke tipe FOH
        7. Hapus data kalkulasi lama, lalu buat data baru
        8. Redirect ke list view az.foh.calculation
        """

        # ensure_one() → memastikan wizard ini hanya dijalankan untuk 1 record.
        # Jika ada lebih dari 1 record aktif, Odoo akan raise error.
        # Ini adalah best practice di Odoo untuk method yang tidak mendukung multi-record.
        self.ensure_one()

        # Validasi sederhana: tanggal awal tidak boleh lebih besar dari tanggal akhir.
        # UserError adalah exception khusus Odoo yang akan tampil sebagai notifikasi
        # di UI (tidak crash), dan _() digunakan untuk mendukung terjemahan (i18n).
        if self.from_date > self.to_date:
            raise UserError(_("From Date cannot be greater than To Date."))

        # ─────────────────────────────────────────────────────────────
        # STEP 1: Ambil data Production Order yang sudah selesai
        # ─────────────────────────────────────────────────────────────
        # self.env['mrp.production'] → mengakses model mrp.production (Manufacturing Order)
        # .search([...]) → mencari record dengan filter/domain berupa list of tuples
        # Filter yang digunakan:
        #   - state = 'done'          → hanya ambil yang sudah selesai diproduksi
        #   - date_start >= from_date → tanggal mulai produksi dalam rentang periode
        #   - date_start <= to_date
        #   - location_dest_id        → lokasi tujuan hasil produksi sesuai input wizard
        productions = self.env['mrp.production'].search([
            ('state', '=', 'done'),
            ('date_start', '>=', self.from_date),
            ('date_start', '<=', self.to_date),
            ('location_dest_id', '=', self.location_id.id),
        ])

        # Jika tidak ada data produksi ditemukan → tampilkan error ke user
        if not productions:
            raise UserError(_("No finished production orders found for the given parameters."))

        # ─────────────────────────────────────────────────────────────
        # STEP 2: Akumulasi (gabungkan) qty_producing per produk
        # ─────────────────────────────────────────────────────────────
        # defaultdict(lambda: {...}) → dictionary dengan nilai default berupa dict kosong.
        # Setiap kali kita akses key yang belum ada, ia otomatis diisi dengan template:
        #   {'qty_raf': 0.0, 'uom_id': False}
        # Ini mencegah KeyError saat pertama kali kita akses pid yang belum terdaftar.
        product_data = defaultdict(lambda: {
            'qty_raf': 0.0,   # qty hasil produksi (RAF = Real Actual Finish)
            'uom_id': False,  # satuan unit produk (Unit of Measure)
        })

        for prod in productions:
            # Gunakan product_id.id (integer) sebagai key agar unik per produk
            pid = prod.product_id.id

            # Akumulasi quantity: jika produk yang sama muncul di beberapa
            # production order, jumlahkan semua qty-nya
            product_data[pid]['qty_raf'] += prod.qty_producing

            # Simpan uom_id hanya sekali (ambil dari production order pertama).
            # Diasumsikan semua production order untuk produk yang sama
            # menggunakan UOM yang sama.
            if not product_data[pid]['uom_id']:
                product_data[pid]['uom_id'] = prod.product_id.uom_id.id

        # ─────────────────────────────────────────────────────────────
        # STEP 3: Ambil rasio FOH per produk dari master az.item.foh.ratio
        # ─────────────────────────────────────────────────────────────
        # Cari semua record ratio yang product_id-nya ada di list produk kita.
        # 'in' di domain Odoo → setara WHERE product_id IN (1, 2, 3, ...)
        # product_data.keys() → menghasilkan list ID produk yang sudah dikumpulkan di step 2
        ratio_records = self.env['az.item.foh.ratio'].search([
            ('product_id', 'in', list(product_data.keys())),
        ])

        # Buat dictionary sederhana: {product_id: ratio}
        # Ini disebut "lookup dict" / "map" → untuk pencarian O(1) berdasarkan product_id
        # Menggunakan dict comprehension (cara ringkas membuat dict dari iterable)
        ratio_map = {r.product_id.id: r.ratio for r in ratio_records}

        # Hitung prod_equ per produk
        for pid, data in product_data.items():
            # .get(pid, 0.0) → ambil nilai dari ratio_map berdasarkan pid.
            # Jika pid tidak ada di ratio_map, gunakan default 0.0 (bukan error).
            ratio = ratio_map.get(pid, 0.0)

            # Simpan ratio ke dalam data produk
            data['ratio'] = ratio

            # prod_equ = production equivalent → qty dikalikan ratio bobot
            # Misalnya: produk A = 100 kg × ratio 1.2 → prod_equ = 120
            data['prod_equ'] = data['qty_raf'] * ratio

        # ─────────────────────────────────────────────────────────────
        # STEP 4: Hitung total prod_equ → lalu bobot proporsi tiap produk
        # ─────────────────────────────────────────────────────────────
        # Jumlahkan semua prod_equ dari semua produk menggunakan generator expression.
        # Contoh: produk A=120, B=80, C=200 → total = 400
        total_prod_equ = sum(d['prod_equ'] for d in product_data.values())

        for pid, data in product_data.items():
            # prod_equ_weight = proporsi/bobot produk ini terhadap total
            # Contoh: produk A = 120 / 400 = 0.30 (30% dari total biaya FOH)
            # Guard: jika total_prod_equ = 0 (semua ratio 0), set weight ke 0
            # untuk menghindari ZeroDivisionError
            if total_prod_equ:
                data['prod_equ_weight'] = data['prod_equ'] / total_prod_equ
            else:
                data['prod_equ_weight'] = 0.0

        # ─────────────────────────────────────────────────────────────
        # STEP 5: Ambil total biaya COA per tipe FOH dari account.move.line
        # ─────────────────────────────────────────────────────────────
        # Ambil semua mapping akun COA ke tipe FOH, kecuali yang bertipe 'none'
        mapping_records = self.env['az.mapping.account.foh'].search([
            ('type', '!=', 'none'),
        ])

        # Bangun dictionary: {foh_type: [account_id, account_id, ...]}
        # Satu tipe FOH bisa memiliki lebih dari satu akun COA.
        # Contoh hasil: {'electricity': [101, 102], 'wage': [201], 'fuel': [301, 302]}
        type_account_map = defaultdict(list)  # default value = [] (list kosong)
        for m in mapping_records:
            # append() menambahkan account_id ke dalam list tipe yang sesuai
            type_account_map[m.type].append(m.account_id.id)

        # Hitung total amount dari journal entries per tipe FOH
        coa_amounts = {}  # hasil akhir: {foh_type: total_amount}
        for foh_type, account_ids in type_account_map.items():
            # Guard: jika list account_ids kosong, set 0 dan lanjut ke tipe berikutnya
            # 'continue' → skip sisa kode dalam loop, langsung ke iterasi berikutnya
            if not account_ids:
                coa_amounts[foh_type] = 0.0
                continue

            # Cari semua baris jurnal (account.move.line) yang memenuhi kriteria:
            #   - account_id ada dalam list akun FOH tipe ini
            #   - tanggal dalam rentang periode wizard
            #   - perusahaan sesuai input wizard
            #   - status journal entry = 'posted' (sudah divalidasi, bukan draft)
            move_lines = self.env['account.move.line'].search([
                ('account_id', 'in', account_ids),
                ('date', '>=', self.from_date),
                ('date', '<=', self.to_date),
                ('company_id', '=', self.company_id.id),
                ('parent_state', '=', 'posted'),
            ])

            # Hitung net amount = debit - credit untuk setiap baris jurnal,
            # lalu jumlahkan semua menggunakan generator expression.
            # Dalam akuntansi: biaya/expense biasanya di sisi debit,
            # sehingga debit - credit menghasilkan nilai positif untuk biaya.
            coa_amounts[foh_type] = sum(
                line.debit - line.credit for line in move_lines
            )

        # ─────────────────────────────────────────────────────────────
        # STEP 6: Hapus data kalkulasi lama untuk periode yang sama
        # ─────────────────────────────────────────────────────────────
        # Sebelum membuat data baru, hapus dulu data lama di periode yang sama.
        # Ini memastikan tidak ada duplikasi data saat wizard dijalankan ulang.
        # .unlink() → method Odoo untuk menghapus record dari database.
        # Pola ini disebut "delete-then-recreate" atau "upsert-style".
        self.env['az.foh.calculation'].search([
            ('trans_date', '>=', self.from_date),
            ('trans_date', '<=', self.to_date),
        ]).unlink()

        # ─────────────────────────────────────────────────────────────
        # STEP 7: Buat record az.foh.calculation baru (batch create)
        # ─────────────────────────────────────────────────────────────
        # Kita kumpulkan semua nilai dulu ke dalam list (vals_list),
        # baru kemudian buat semua sekaligus dengan .create(vals_list).
        # Ini lebih efisien daripada .create() satu per satu dalam loop
        # karena mengurangi jumlah query ke database.
        vals_list = []
        # Compute trans_date = last day of from_date's month
        from datetime import date as dt_date
        last_day = calendar.monthrange(self.from_date.year, self.from_date.month)[1]
        trans_date = dt_date(self.from_date.year, self.from_date.month, last_day)

        for pid, data in product_data.items():
            prod_equ_weight = data['prod_equ_weight']

            # Duplicate validation per product
            product_name = self.env['product.product'].browse(pid).display_name
            if self.env['az.foh.calculation'].search([
                ('product_id', '=', pid),
                ('trans_date', '=', trans_date),
                ('location_id', '=', self.location_id.id),
            ], limit=1):
                raise ValidationError(
                    _("FOH Calculation already exists for product '%s' on %s.\n"
                      "Please delete existing data first.") % (product_name, trans_date)
                )

            # Siapkan dictionary nilai untuk satu record az.foh.calculation
            vals = {
                'trans_date': trans_date,
                'location_id': self.location_id.id,
                'company_id': self.company_id.id,
                'product_id': pid,
                'qty_raf': data['qty_raf'],             # total qty produksi
                'uom': data['uom_id'],                 # satuan qty_raf
                'qty_raf_convert': data['qty_raf'],    # qty setelah konversi (saat ini sama)
                'uom_convert': data['uom_id'],         # satuan qty_raf_convert
                'ratio': data['ratio'],                # rasio bobot dari master
                'prod_equ': data['prod_equ'],          # qty × ratio
                'prod_equ_weight': prod_equ_weight,    # proporsi produk ini (0.0 - 1.0)
            }

            # Loop semua tipe FOH untuk mengisi field percent_* dan amount_*
            for foh_type in FOH_TYPES:
                # Dapatkan suffix field dari FOH_FIELD_MAP
                # Contoh: foh_type='work_order' → field_suffix='workorder'
                field_suffix = FOH_FIELD_MAP[foh_type]

                # Ambil total biaya COA tipe ini (default 0 jika tidak ada)
                coa_amount = coa_amounts.get(foh_type, 0.0)

                # Hitung persentase produk ini dari total (dalam %)
                # Contoh: prod_equ_weight=0.30 → percent=30.0
                percent = prod_equ_weight * 100

                # Hitung bagian biaya FOH untuk produk ini
                # amount = (percent / 100) × total_biaya_tipe_ini
                # Contoh: (30 / 100) × 5.000.000 = 1.500.000
                amount = (percent / 100.0) * coa_amount

                # Isi field dinamis menggunakan f-string
                # Contoh: vals['percent_electricity'] = 30.0
                #         vals['amount_electricity']  = 1500000.0
                vals[f'percent_{field_suffix}'] = percent
                vals[f'amount_{field_suffix}'] = amount

            # Tambahkan dictionary vals produk ini ke dalam list
            vals_list.append(vals)

        # Buat semua record sekaligus (batch insert) → lebih efisien
        self.env['az.foh.calculation'].create(vals_list)

        # ─────────────────────────────────────────────────────────────
        # STEP 8: Return action untuk membuka list view hasil kalkulasi
        # ─────────────────────────────────────────────────────────────
        # Setelah selesai, wizard akan menutup dirinya dan membuka
        # list view dari model az.foh.calculation.
        # Ini adalah pola standar Odoo untuk redirect setelah aksi wizard selesai:
        #   - type: 'ir.actions.act_window' → aksi membuka window/view
        #   - res_model: model yang akan ditampilkan
        #   - view_mode: urutan tampilan yang tersedia (list dulu, baru form)
        #   - target: 'current' → buka di tab/window yang sama (bukan popup)
        return {
            'type': 'ir.actions.act_window',
            'name': _('FOH Calculation'),
            'res_model': 'az.foh.calculation',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def remove_mrp_inventory_data_wizard(self):
        """
        Remove all FOH, MRP, and Inventory transactional data.
        Exposed as a danger button on the FOH Calculation wizard.
        """
        import logging
        _logger = logging.getLogger(__name__)

        try:
            self._cr.execute("SET CONSTRAINTS ALL DEFERRED")

            # 1. FOH transactional tables (child → parent)
            for table in [
                'az_foh_cost_price_fg',
                'az_foh_production_price',
                'az_foh_production_cost',
                'az_foh_item_cost_price',
                'az_foh_calculation',
            ]:
                _logger.info("Deleting %s...", table)
                self._cr.execute(f"DELETE FROM {table}")  # noqa: S608

            # Legacy table — skip gracefully if already dropped
            self._cr.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'az_foh_mrp_cost_price'
                    ) THEN
                        DELETE FROM az_foh_mrp_cost_price;
                    END IF;
                END$$
            """)

            # 2. MRP data (child → parent)
            _logger.info("Deleting MRP data...")
            self._cr.execute("DELETE FROM mrp_workcenter_productivity")
            self._cr.execute("DELETE FROM mrp_workorder")
            self._cr.execute("""
                DELETE FROM stock_move_line
                WHERE move_id IN (
                    SELECT sm.id FROM stock_move sm
                    JOIN mrp_production mp
                      ON sm.raw_material_production_id = mp.id
                      OR sm.production_id = mp.id
                )
            """)
            self._cr.execute("""
                DELETE FROM stock_move
                WHERE raw_material_production_id IS NOT NULL
                   OR production_id IS NOT NULL
            """)
            self._cr.execute("DELETE FROM mrp_production")

            # 3. General inventory
            _logger.info("Deleting inventory data...")
            self._cr.execute("DELETE FROM stock_move_line")
            self._cr.execute("DELETE FROM stock_move")
            self._cr.execute("DELETE FROM stock_picking")
            self._cr.execute("""
                DELETE FROM stock_quant
                WHERE location_id IN (
                    SELECT id FROM stock_location WHERE usage = 'internal'
                )
            """)
            self._cr.execute("DELETE FROM stock_valuation_layer")

            # 4. Reset sequences
            self._cr.execute("""
                UPDATE ir_sequence
                SET number_next = 1
                WHERE code LIKE 'mrp.%'
                   OR code LIKE 'stock.%'
                   OR prefix LIKE 'WH/%'
            """)

            self._cr.commit()
            _logger.info("All MRP and Inventory data removed successfully.")

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("All MRP and Inventory data has been removed successfully."),
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as e:
            self._cr.rollback()
            _logger.error("Error removing data: %s", str(e))
            raise UserError(_("Error removing data: %s") % str(e))
