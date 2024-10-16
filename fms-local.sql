DROP SCHEMA IF EXISTS fms;
CREATE SCHEMA fms;
USE jiaruizhang11619$fms;

DROP TABLE IF EXISTS curr_date;
CREATE TABLE IF NOT EXISTS curr_date (
    curr_date DATE NOT NULL,
    PRIMARY KEY (curr_date)
);

INSERT INTO curr_date VALUES
    ("2024-10-29") ON DUPLICATE KEY UPDATE curr_date="2024-10-29";

DROP TABLE IF EXISTS paddocks;
CREATE TABLE IF NOT EXISTS paddocks (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    area FLOAT(2) NOT NULL,
    dm_per_ha FLOAT(2) NOT NULL,
    total_dm FLOAT(2) AS (area * dm_per_ha) STORED,
    PRIMARY KEY (id)
);

INSERT INTO paddocks (name, area, dm_per_ha, total_dm) VALUES
    ("Stream 1", 1.22, 1500, 1.22 * 1500),
    ("Rear 1", 1.23, 2300, 1.23 * 2300),
    ("Rear 2", 1.15, 1900, 1.15 * 1900),
    ("Barn", 0.95, 1750, 0.95 * 1750)
    ON DUPLICATE KEY UPDATE name=VALUES(name), area=VALUES(area), dm_per_ha=VALUES(dm_per_ha), total_dm=VALUES(total_dm);

DROP TABLE IF EXISTS mobs;
CREATE TABLE IF NOT EXISTS mobs (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) DEFAULT NULL,
    paddock_id INT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE INDEX paddock_idx (paddock_id),
    CONSTRAINT fk_paddock FOREIGN KEY (paddock_id)
        REFERENCES paddocks (id)
        ON DELETE NO ACTION ON UPDATE NO ACTION
);

INSERT INTO mobs (name, paddock_id) VALUES
    ("Mob 1", 4),
    ("Mob 2", 1),
    ("Mob 3", 2)
    ON DUPLICATE KEY UPDATE name=VALUES(name), paddock_id=VALUES(paddock_id);

DROP TABLE IF EXISTS stock;
CREATE TABLE IF NOT EXISTS stock (
    id INT NOT NULL AUTO_INCREMENT,
    mob_id INT DEFAULT NULL,
    dob DATE NOT NULL,
    weight FLOAT(2) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_mob FOREIGN KEY (mob_id)
        REFERENCES mobs (id)
        ON DELETE NO ACTION ON UPDATE NO ACTION
);

INSERT INTO stock (mob_id, dob, weight) VALUES
    (1, '2022-07-25', 586.3),
    (2, '2023-08-22', 311.2),
    (7, '2023-09-17', 293),
    (1, '2022-08-16', 570.9),
    (2, '2023-11-01', 261.5),
    (7, '2023-09-26', 286.7),
    (1, '2022-08-24', 565.3),
    (7, '2023-09-03', 302.8),
    (7, '2023-09-24', 288.1),
    (1, '2022-09-09', 554.1),
    (2, '2023-08-07', 321.7),
    (2, '2023-08-13', 317.5),
    (1, '2022-09-14', 550.6),
    (7, '2023-09-20', 290.9),
    (7, '2023-09-10', 297.9),
    (1, '2022-10-30', 518.4),
    (2, '2023-07-16', 337.1),
    (2, '2023-07-15', 337.8),
    (7, '2023-10-06', 279.7),
    (1, '2022-08-27', 563.2),
    (7, '2023-09-10', 297.9),
    (1, '2022-09-30', 539.4),
    (2, '2023-07-15', 337.8),
    (1, '2022-08-24', 565.3),
    (1, '2022-09-03', 558.3),
    (7, '2023-09-24', 288.1)
    ON DUPLICATE KEY UPDATE mob_id=VALUES(mob_id), dob=VALUES(dob), weight=VALUES(weight);