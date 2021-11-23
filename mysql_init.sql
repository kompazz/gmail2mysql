create database gmail2mysql CHARACTER SET utf8mb4;;
use gmail2mysql;

create table mails (
id int,
title text,
inbox varchar(255),
from_addr text, 
to_addr text,
cc text, 
date datetime, 
body text,
primary key(id, inbox))
;

create table attachments(
id int primary key auto_increment,
file_name text,
file_content longblob,
mail_id int,
mail_inbox varchar(255),
foreign key (mail_id, mail_inbox)
references mails(id, inbox));