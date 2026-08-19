-- DROP DATABASE alibaba;
CREATE DATABASE IF NOT EXISTS alibaba;

USE alibaba;

CREATE TABLE
    IF NOT EXISTS companies (
        id INT AUTO_INCREMENT PRIMARY KEY,
        company_name VARCHAR(255),
        company_url VARCHAR(255) NOT NULL UNIQUE,
        date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

CREATE TABLE
    IF NOT EXISTS scrape_tracking (
        id INT AUTO_INCREMENT PRIMARY KEY,
        company_url VARCHAR(255) NOT NULL,
        item_name VARCHAR(1000) NOT NULL,
        item_url VARCHAR(700) NOT NULL UNIQUE,
        category VARCHAR(700) NOT NULL,
        scrape_status VARCHAR(50),
        server_ip VARCHAR(50),
        error_message VARCHAR(5000),
        date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        scrape_result JSON,
        FOREIGN KEY (company_url) REFERENCES companies (company_url)
    );

CREATE TABLE
    IF NOT EXISTS server_status (
        id INT AUTO_INCREMENT PRIMARY KEY,
        server_ip VARCHAR(50),
        server_action VARCHAR(5000),
        server_action_details VARCHAR(5000),
        date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

CREATE TABLE
    IF NOT EXISTS server_details (
        id INT AUTO_INCREMENT PRIMARY KEY,
        server_ip VARCHAR(50),
        server_name VARCHAR(5000)
    );