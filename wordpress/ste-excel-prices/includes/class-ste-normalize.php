<?php

if (!defined('ABSPATH')) {
    exit;
}

class STE_Normalize {
    public static function fold($text) {
        $map = array(
            'ك' => 'ک', 'ي' => 'ی', 'ى' => 'ی', 'ة' => 'ه',
            '۰' => '0', '۱' => '1', '۲' => '2', '۳' => '3', '۴' => '4',
            '۵' => '5', '۶' => '6', '۷' => '7', '۸' => '8', '۹' => '9',
            '٠' => '0', '١' => '1', '٢' => '2', '٣' => '3', '٤' => '4',
            '٥' => '5', '٦' => '6', '٧' => '7', '٨' => '8', '٩' => '9',
            'پالستیک' => 'پلاستیک',
        );
        $text = strtr((string) $text, $map);
        $text = preg_replace('/\s+/u', ' ', $text);
        return trim($text);
    }

    public static function name($text) {
        $text = self::fold($text);
        $text = mb_strtolower($text, 'UTF-8');
        $text = str_replace('آ', 'ا', $text);
        $text = preg_replace('/[()\[\]{},.;:|\\\'\"«»]+/u', ' ', $text);
        return trim(preg_replace('/\s+/u', ' ', $text));
    }

    public static function money($value) {
        if ($value === null || $value === '' || $value === '-') {
            return null;
        }
        $text = self::fold((string) $value);
        $text = str_replace(array(',', '٬', '،', ' '), '', $text);
        if (!is_numeric($text)) {
            return null;
        }
        return (int) round((float) $text);
    }
}
