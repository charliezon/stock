-- MySQL dump 10.13  Distrib 5.7.16, for Win64 (x86_64)
--
-- Host: localhost    Database: stock
-- ------------------------------------------------------
-- Server version	5.7.16-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `account_asset_change`

use stock;
--

DROP TABLE IF EXISTS `account_asset_change`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `account_asset_change` (
  `id` varchar(50) NOT NULL,
  `account_id` varchar(50) NOT NULL,
  `change_amount` double NOT NULL,
  `operation` int(10) NOT NULL,
  `security_or_bank` tinyint(1) DEFAULT NULL,
  `date` varchar(50) NOT NULL,
  `created_at` double NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `account_asset_change`
--

LOCK TABLES `account_asset_change` WRITE;
/*!40000 ALTER TABLE `account_asset_change` DISABLE KEYS */;
INSERT INTO `account_asset_change` VALUES ('0014793008589663b44d68a56874cd59d6c896962c03d82000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,0,1,'2016-11-16',1479300858.96628),('001479300858981fcb9f81c6dfd45d6a0803c4153723edd000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,1,0,'2016-11-16',1479300858.9819),('00147930087000149397244ee7143d8a74d081462fab079000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,1,1,'2016-11-16',1479300870.00128),('0014793008700165e1cdd378bc14422950caad7bb78e640000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,0,0,'2016-11-16',1479300870.01691),('0014793009496282606f77d358141dea4b12707d6a9b28d000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,1,0,'2016-11-16',1479300949.62809),('001479300967426897316b920ef4b05b7a9999aa50e35f7000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,0,0,'2016-11-16',1479300967.42653),('001479301084746591f1af551114842a89d3f191e67a219000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,1,0,'2016-11-16',1479301084.74646),('001479301094474f46eb39d58a5464aa8e0f4e55be6abd0000','0014793003162807286dc3299d348c3879c710a986a30c3000',1,0,0,'2016-11-16',1479301094.47449);
/*!40000 ALTER TABLE `account_asset_change` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `account_records`
--

DROP TABLE IF EXISTS `account_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `account_records` (
  `id` varchar(50) NOT NULL,
  `date` varchar(50) NOT NULL,
  `account_id` varchar(50) NOT NULL,
  `stock_position` double NOT NULL,
  `security_funding` double NOT NULL,
  `bank_funding` double NOT NULL,
  `total_stock_value` double NOT NULL,
  `total_assets` double NOT NULL,
  `float_profit_lost` double NOT NULL,
  `total_profit` double NOT NULL,
  `principle` double NOT NULL,
  `created_at` double NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `account_records`
--

LOCK TABLES `account_records` WRITE;
/*!40000 ALTER TABLE `account_records` DISABLE KEYS */;
INSERT INTO `account_records` VALUES ('0014793003162800920b748e6c64f5ca5c6c52d88fbd0a5000','2016-11-16','0014793003162807286dc3299d348c3879c710a986a30c3000',0.2267,140438.23,0,41174,181612.23,-489.62,-18387.77,200000,1479300316.28061);
/*!40000 ALTER TABLE `account_records` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `accounts`
--

DROP TABLE IF EXISTS `accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `accounts` (
  `id` varchar(50) NOT NULL,
  `user_id` varchar(50) NOT NULL,
  `name` varchar(50) NOT NULL,
  `commission_rate` double NOT NULL,
  `initial_funding` double NOT NULL,
  `created_at` double NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `accounts`
--

LOCK TABLES `accounts` WRITE;
/*!40000 ALTER TABLE `accounts` DISABLE KEYS */;
INSERT INTO `accounts` VALUES ('0014793003162807286dc3299d348c3879c710a986a30c3000','0014793002621243c1c1b1c205144478a7ab428ac6f36f4000','同花顺模拟炒股',0.001,200000,1479300316.28061);
/*!40000 ALTER TABLE `accounts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `market_state`
--

DROP TABLE IF EXISTS `market_state`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `market_state` (
  `date` varchar(50) NOT NULL,
  `market_state` int(10) NOT NULL,
  PRIMARY KEY (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `market_state`
--

LOCK TABLES `market_state` WRITE;
/*!40000 ALTER TABLE `market_state` DISABLE KEYS */;
/*!40000 ALTER TABLE `market_state` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stock_hold_records`
--

DROP TABLE IF EXISTS `stock_hold_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `stock_hold_records` (
  `id` varchar(50) NOT NULL,
  `account_record_id` varchar(50) NOT NULL,
  `stock_code` varchar(50) NOT NULL,
  `stock_name` varchar(50) NOT NULL,
  `stock_amount` int(100) NOT NULL,
  `stock_current_price` double NOT NULL,
  `stock_buy_price` double NOT NULL,
  `stock_sell_price` double NOT NULL,
  `stock_buy_date` varchar(50) NOT NULL,
  `created_at` double NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stock_hold_records`
--

LOCK TABLES `stock_hold_records` WRITE;
/*!40000 ALTER TABLE `stock_hold_records` DISABLE KEYS */;
INSERT INTO `stock_hold_records` VALUES ('001479300360898cc1e5faaba9e4e77ae8118c7e3f53167000','0014793003162800920b748e6c64f5ca5c6c52d88fbd0a5000','300431','暴风集团',700,58.82,59.46,62.3,'2016-11-16',1479300360.89898);
/*!40000 ALTER TABLE `stock_hold_records` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `users` (
  `id` varchar(50) NOT NULL,
  `email` varchar(50) NOT NULL,
  `passwd` varchar(50) NOT NULL,
  `admin` tinyint(1) NOT NULL,
  `name` varchar(50) NOT NULL,
  `image` varchar(500) NOT NULL,
  `created_at` double NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_name` (`name`),
  UNIQUE KEY `idx_email` (`email`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES ('0014793002621243c1c1b1c205144478a7ab428ac6f36f4000','test@gmail.com','14bc305cad2e7340f1592f794814140ac7d8f30e',1,'charlie','http://www.gravatar.com/avatar/593638ac6a1730571c846c1efeef9873?d=mm&s=120',1479300262.12498);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2016-11-16 22:38:18
