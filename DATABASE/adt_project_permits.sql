-- MySQL dump 10.13  Distrib 8.0.43, for Win64 (x86_64)
--
-- Host: localhost    Database: adt_project
-- ------------------------------------------------------
-- Server version	8.0.43

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `permits`
--

DROP TABLE IF EXISTS `permits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `permits` (
  `permit_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  PRIMARY KEY (`permit_id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `permits`
--

LOCK TABLES `permits` WRITE;
/*!40000 ALTER TABLE `permits` DISABLE KEYS */;
INSERT INTO `permits` VALUES (1,'Accessible Metered Parking'),(2,'Accessible Parking'),(3,'Accessible Pay Parking'),(4,'Athletic Parking'),(7,'Campus Housing Parking - Zone 1'),(8,'Campus Housing Parking - Zone 1 & 2'),(9,'Campus Housing Parking - Zone 2'),(10,'Campus Housing Parking - Zone 3'),(11,'Campus Housing Parking - Zone 4'),(12,'Campus Housing Parking - Zone 5'),(13,'Campus Housing Parking - Zone 6'),(14,'Campus Housing Parking - Zone 7'),(6,'CH6 Parking'),(21,'Electric Veh Parking'),(15,'EM Retired Parking'),(16,'EMP Parking'),(17,'EMP Parking (24 Hr)'),(18,'EMS Parking'),(19,'EMS Parking (24 Hr)'),(20,'EMS Parking (Upper Level only)'),(22,'IU Foundation Parking'),(23,'Metered Parking'),(24,'Motor Pool Vehicle Parking'),(25,'Motorcycle Parking'),(26,'Patient Parking'),(27,'Real Estate Office Parking'),(28,'Reserved Parking'),(29,'Service Vehicle Parking'),(30,'Student Parking'),(31,'Student Parking Section'),(32,'Student Parking Section E ONLY'),(33,'This is all of David Baker Ave Street Parking'),(34,'Visitor Parking'),(35,'Visitor Pay Lot'),(36,'Visitor Pay Parking'),(37,'Visitor Pay Parking (Upper Level Only)');
/*!40000 ALTER TABLE `permits` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-12-14 23:05:25
