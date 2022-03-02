Saves gmail inbox and outbox emails with attachments to mysql.
State of imported emails is stored in settings.ini section Boxes.

Install:

`pip3 install -r requirements.txt`

Setup:

1. In mysql run mysql_init.sql to create database and tables
2. Fill settings.ini with your gmail and mysql credentials
3. Enable external applications on your gmail account


Usage:

`python3 gmail_to_mysql.py`


Known issues:

Encoding - some messages are saved with html code instead of just the text. Fix is welcome
