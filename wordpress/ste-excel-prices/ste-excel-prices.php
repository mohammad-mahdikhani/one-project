<?php
/**
 * Plugin Name: استی — قیمت تلگرام و اکسل
 * Description: قیمت کانال تلگرام یا فایل اکسل/PDF را با کد و اسم کالای ووکامرس تطبیق می‌دهد و روی سایت به‌روز می‌کند.
 * Version: 1.0.0
 * Author: استی
 * Text Domain: ste-excel-prices
 */

if (!defined('ABSPATH')) {
    exit;
}

define('STE_PRICE_DIR', plugin_dir_path(__FILE__));
define('STE_PRICE_URL', plugin_dir_url(__FILE__));

require_once STE_PRICE_DIR . 'includes/class-ste-normalize.php';
require_once STE_PRICE_DIR . 'includes/class-ste-matcher.php';
require_once STE_PRICE_DIR . 'includes/class-ste-reader.php';
require_once STE_PRICE_DIR . 'includes/class-ste-admin.php';

add_action('plugins_loaded', static function () {
    if (class_exists('WooCommerce')) {
        STE_Admin::init();
    }
});
