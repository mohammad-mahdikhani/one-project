<?php

if (!defined('ABSPATH')) {
    exit;
}

class STE_Reader {
    public static function rows_from_upload($file) {
        $name = strtolower($file['name']);
        if (str_ends_with($name, '.csv')) {
            return self::csv($file['tmp_name']);
        }
        if (str_ends_with($name, '.xlsx')) {
            return self::xlsx($file['tmp_name']);
        }
        throw new Exception('فقط اکسل xlsx یا csv.');
    }

    private static function csv($path) {
        $handle = fopen($path, 'r');
        $header = fgetcsv($handle);
        $map = self::map_header($header);
        $rows = array();
        $index = 1;
        while (($line = fgetcsv($handle)) !== false) {
            $index++;
            $row = self::mapped_row($map, $line, $index);
            if ($row) {
                $rows[] = $row;
            }
        }
        fclose($handle);
        return $rows;
    }

    private static function xlsx($path) {
        $zip = new ZipArchive();
        if ($zip->open($path) !== true) {
            throw new Exception('فایل اکسل باز نشد');
        }
        $shared = array();
        $xml = $zip->getFromName('xl/sharedStrings.xml');
        if ($xml) {
            preg_match_all('/<t[^>]*>(.*?)<\/t>/s', $xml, $matches);
            $shared = array_map('html_entity_decode', $matches[1]);
        }
        $sheet = $zip->getFromName('xl/worksheets/sheet1.xml');
        $zip->close();
        preg_match_all('/<row[^>]*>(.*?)<\/row>/s', $sheet, $row_match);
        $table = array();
        foreach ($row_match[1] as $row_xml) {
            $cells = array();
            if (preg_match_all('/<c([^>]*)>(?:<v>(.*?)<\/v>)?/s', $row_xml, $cell_match, PREG_SET_ORDER)) {
                foreach ($cell_match as $cell) {
                    $value = isset($cell[2]) ? $cell[2] : '';
                    if (strpos($cell[1], 't="s"') !== false && isset($shared[(int) $value])) {
                        $value = $shared[(int) $value];
                    }
                    $cells[] = html_entity_decode($value);
                }
            }
            $table[] = $cells;
        }
        if (!$table) {
            throw new Exception('شیت خالی است');
        }
        $map = self::map_header($table[0]);
        $rows = array();
        foreach (array_slice($table, 1) as $i => $line) {
            $row = self::mapped_row($map, $line, $i + 2);
            if ($row) {
                $rows[] = $row;
            }
        }
        return $rows;
    }

    private static function map_header($header) {
        $aliases = array(
            'name' => array('name', 'شرح', 'شرح کالا', 'نام', 'نام کالا', 'عنوان'),
            'sku' => array('sku', 'کد', 'کد کالا', 'کد محصول'),
            'price' => array('price', 'قیمت', 'مصرف کننده', 'قیمت مصرف کننده'),
        );
        $map = array();
        foreach ((array) $header as $index => $cell) {
            $key = STE_Normalize::fold($cell);
            foreach ($aliases as $field => $names) {
                if (in_array($key, $names, true)) {
                    $map[$field] = $index;
                }
            }
        }
        if (!isset($map['name'])) {
            $map = array('sku' => 1, 'name' => 2, 'price' => 3);
        }
        return $map;
    }

    private static function mapped_row($map, $line, $index) {
        $name = STE_Normalize::fold($line[$map['name']] ?? '');
        if ($name === '') {
            return null;
        }
        return array(
            'row' => $index,
            'name' => $name,
            'sku' => STE_Normalize::fold($line[$map['sku']] ?? ''),
            'price' => STE_Normalize::money($line[$map['price']] ?? null),
        );
    }
}
