-- schema.sql

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
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table account_records (
    `id` varchar(50) not null,
    `account_id` varchar(50) not null,
    `market_condition` int(2) not null,
    `stock_position` real not null,
    `available_funding` real not null,
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
    `stock_buy_date` real not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table account_asset_change (
    `id` varchar(50) not null,
    `account_id` varchar(50) not null,
    `asset_change` real not null,
    `add_or_minus` bool null,
    `change_date` real not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;