<?php

if (!defined('ABSPATH')) {
    exit;
}

class STE_Admin {
    public static function init() {
        add_action('admin_menu', array(self::class, 'menu'));
        add_action('admin_enqueue_scripts', array(self::class, 'assets'));
        add_action('wp_ajax_ste_preview', array(self::class, 'preview'));
        add_action('wp_ajax_ste_apply', array(self::class, 'apply'));
    }

    public static function menu() {
        add_submenu_page(
            'woocommerce',
            'استی قیمت',
            'استی قیمت',
            'manage_woocommerce',
            'ste-excel-prices',
            array(self::class, 'page')
        );
    }

    public static function assets($hook) {
        if (strpos((string) $hook, 'ste-excel-prices') === false) {
            return;
        }
        wp_enqueue_style('ste-excel-prices', STE_PRICE_URL . 'assets/admin.css', array(), '1.0.0');
        wp_enqueue_script('ste-excel-prices', STE_PRICE_URL . 'assets/admin.js', array(), '1.0.0', true);
        wp_localize_script('ste-excel-prices', 'stePrice', array(
            'ajax' => admin_url('admin-ajax.php'),
            'nonce' => wp_create_nonce('ste_price'),
        ));
    }

    public static function page() {
        echo '<div class="wrap ste-wrap"><h1>استی — تطبیق قیمت اکسل با ووکامرس</h1>';
        echo '<p>خزش کانال تلگرام در برنامه استی انجام می‌شود. نتیجه یا فایل اکسل را اینجا بدهید تا با اسم و کد کالای سایت جفت شود.</p>';
        echo '<form id="ste-form"><input type="file" name="file" accept=".xlsx,.csv" required> ';
        echo '<label><input type="checkbox" name="create_missing"> کالای جدید بساز</label> ';
        echo '<button class="button button-primary">پیش‌نمایش</button></form>';
        echo '<div id="ste-stats"></div><table class="widefat" id="ste-table" hidden><thead><tr><th>وضعیت</th><th>شیت</th><th>سایت</th><th>قیمت جدید</th></tr></thead><tbody></tbody></table>';
        echo '<p><button class="button button-primary" id="ste-apply" hidden>اعمال روی سایت</button></p></div>';
    }

    private static function products() {
        $items = array();
        $query = wc_get_products(array('limit' => -1, 'status' => array('publish', 'draft')));
        foreach ($query as $product) {
            $items[] = array(
                'id' => $product->get_id(),
                'name' => $product->get_name(),
                'sku' => (string) $product->get_sku(),
                'price' => STE_Normalize::money($product->get_regular_price()),
            );
        }
        return $items;
    }

    public static function preview() {
        check_ajax_referer('ste_price', 'nonce');
        if (empty($_FILES['file'])) {
            wp_send_json_error(array('message' => 'فایل را انتخاب کنید'), 400);
        }
        try {
            $rows = STE_Reader::rows_from_upload($_FILES['file']);
        } catch (Exception $exc) {
            wp_send_json_error(array('message' => $exc->getMessage()), 400);
        }
        $products = self::products();
        $results = array();
        foreach ($rows as $row) {
            $match = STE_Matcher::match_row($row, $products);
            $results[] = array_merge($row, $match);
        }
        wp_send_json_success(array('results' => $results));
    }

    public static function apply() {
        check_ajax_referer('ste_price', 'nonce');
        $payload = json_decode(wp_unslash($_POST['results'] ?? '[]'), true);
        $create = !empty($_POST['create_missing']);
        $updated = 0;
        $created = 0;
        foreach ((array) $payload as $row) {
            if (($row['action'] ?? '') === 'update' && !empty($row['product']['id']) && isset($row['price'])) {
                $product = wc_get_product((int) $row['product']['id']);
                if ($product) {
                    $product->set_regular_price((string) $row['price']);
                    if (!empty($row['sku']) && !$product->get_sku()) {
                        $product->set_sku($row['sku']);
                    }
                    $product->save();
                    $updated++;
                }
            } elseif (($row['action'] ?? '') === 'create' && $create && !empty($row['name']) && isset($row['price'])) {
                $product = new WC_Product_Simple();
                $product->set_name($row['name']);
                $product->set_regular_price((string) $row['price']);
                if (!empty($row['sku'])) {
                    $product->set_sku($row['sku']);
                }
                $product->set_status('publish');
                $product->save();
                $created++;
            }
        }
        wp_send_json_success(array('updated' => $updated, 'created' => $created));
    }
}
