-- schema.sql

-- mysql -uroot -p < schema.sql

drop database if exists stock;

create database stock;

use stock;

create table users (
    `id` varchar(50) not null,
    `email` varchar(50) not null,
    `passwd` varchar(50) not null,
    `admin` bool not null,
    `name` varchar(50) not null,
    `image` varchar(500) not null,
    `created_at` real not null,
    unique key `idx_name` (`name`),
    unique key `idx_email` (`email`),
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table accounts (
    `id` varchar(50) not null,
    `user_id` varchar(50) not null,
    `name` varchar(50) not null,
    `commission_rate` real not null,
    `initial_funding` real not null,
    `success_times` int(100) not null,
    `fail_times` int(100) not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table account_records (
    `id` varchar(50) not null,
    `date` varchar(50) not null,
    `account_id` varchar(50) not null,
    `stock_position` real not null,
    `security_funding` real not null,
    `bank_funding` real not null,
    `total_stock_value` real not null,
    `total_assets` real not null,
    `float_profit_lost` real not null,
    `total_profit` real not null,
    `principle` real not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table stock_hold_records (
    `id` varchar(50) not null,
    `account_record_id` varchar(50) not null,
    `stock_code` varchar(50) not null,
    `stock_name` varchar(50) not null,
    `stock_amount` int(100) not null,
    `stock_current_price` real not null,
    `stock_buy_price` real not null,
    `stock_sell_price` real not null,
    `stock_buy_date` varchar(50) not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table stock_trade_records (
    `id` varchar(50) not null,
    `account_id` varchar(50) not null,
    `stock_code` varchar(50) not null,
    `stock_name` varchar(50) not null,
    `stock_amount` int(100) not null,
    `stock_price` real not null,
    `stock_date` varchar(50) not null,
    `stock_operation` bool null,
    `trade_series` varchar(50) not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table account_asset_change (
    `id` varchar(50) not null,
    `account_id` varchar(50) not null,
    `change_amount` real not null,
    `operation` int(100) not null,
    `security_or_bank` bool null,
    `date` varchar(50) not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table daily_params (
    `date` varchar(50) not null,
    `shanghai_index` real not null,
    `stock_market_status` int(10) not null,
    `twenty_days_line` bool null,
    `increase_range` real not null,
    `three_days_average_shanghai_increase` real not null,
    `shanghai_break_twenty_days_line` bool null,
    `shanghai_break_twenty_days_line_obviously` bool null,
    `shanghai_break_twenty_days_line_for_two_days` bool null,
    `shenzhen_break_twenty_days_line` bool null,
    `shenzhen_break_twenty_days_line_obviously` bool null,
    `shenzhen_break_twenty_days_line_for_two_days` bool null,
    `all_stock_amount` int(100) not null,
    `buy_stock_amount` int(100) not null,
    `buy_stock_ratio` real not null,
    `pursuit_stock_amount` int(100) not null,
    `pursuit_stock_ratio` real not null,
    `iron_stock_amount` int(100) not null,
    `bank_stock_amount` int(100) not null,
    `strong_pursuit_stock_amount` int(100) not null,
    `strong_pursuit_stock_ratio` real not null,
    `pursuit_kdj_die_stock_amount` int(100) not null,
    `pursuit_kdj_die_stock_ratio` real not null,
    `run_stock_amount` int(100) not null,
    `run_stock_ratio` real not null,
    `big_fall_after_multi_bank_iron` bool null,
    `four_days_pursuit_ratio_decrease` bool null,
    `too_big_increase` bool null,
    `futures` varchar(50) not null,
    `method_1` varchar(50) not null,
    `method_2` varchar(50) not null,
    `recommendation` varchar(50) not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`date`)
) engine=innodb default charset=utf8;