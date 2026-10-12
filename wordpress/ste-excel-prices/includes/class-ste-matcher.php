<?php

if (!defined('ABSPATH')) {
    exit;
}

class STE_Matcher {
    public static function tokens($name) {
        $stop = array('دستگاه', 'مدل', 'با', 'و', 'در', 'به', 'از', 'عدد', 'عددی');
        $parts = preg_split('/\s+/u', STE_Normalize::name($name));
        $out = array();
        foreach ($parts as $part) {
            if ($part === '' || in_array($part, $stop, true) || mb_strlen($part, 'UTF-8') < 2) {
                continue;
            }
            $out[] = $part;
        }
        return $out;
    }

    public static function score($sheet_name, $product_name) {
        $a = self::tokens($sheet_name);
        $b = self::tokens($product_name);
        if (!$a || !$b) {
            return 0;
        }
        if (STE_Normalize::name($sheet_name) === STE_Normalize::name($product_name)) {
            return 98;
        }
        $overlap = array_intersect($a, $b);
        if (!$overlap) {
            return 0;
        }
        $dice = 2 * count($overlap) / (count($a) + count($b));
        $recall = count($overlap) / count($a);
        return (int) round(100 * (0.6 * $recall + 0.4 * $dice));
    }

    public static function match_row($row, $products) {
        if (!empty($row['sku'])) {
            foreach ($products as $product) {
                if ($product['sku'] !== '' && $product['sku'] === $row['sku']) {
                    return array('action' => 'update', 'product' => $product, 'score' => 100, 'reason' => 'کد کالا یکی است');
                }
            }
        }
        $best = null;
        $best_score = 0;
        foreach ($products as $product) {
            $score = self::score($row['name'], $product['name']);
            if ($score > $best_score) {
                $best_score = $score;
                $best = $product;
            }
        }
        if ($best && $best_score >= 78) {
            return array('action' => 'update', 'product' => $best, 'score' => $best_score, 'reason' => 'تطابق از روی نام');
        }
        if ($best && $best_score >= 62) {
            return array('action' => 'suggest', 'product' => $best, 'score' => $best_score, 'reason' => 'نام نزدیک است؛ تأیید کنید');
        }
        return array('action' => 'create', 'product' => null, 'score' => $best_score, 'reason' => 'روی سایت پیدا نشد');
    }
}
