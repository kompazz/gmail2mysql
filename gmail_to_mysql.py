import easyimap as e
from configparser import ConfigParser
from configparser import NoSectionError
import mysql.connector
import dateparser
import re, sys
from imaplib import IMAP4


def get_settings():
    parser = ConfigParser()
    parser.read('settings.ini')
    return parser

def gmail_login(settings, mailbox):
    host = settings.get('server', 'SMTP_SERVER')
    user = settings.get('user', 'USER')
    password = settings.get('user', 'PASS')
    try:
        imapper = e.connect(host, user, password, mailbox, ssl=True, read_only=True)
    except NoSectionError:
        print('Brak sekcji server w settings.ini lub braku pliku settings.ini')
        sys.exit()
    except IMAP4.error:
        print('Błędne dane logowania gmail')
        sys.exit()
    print('Zalogowano do gmail')
    return imapper

def connect_mysql(settings):
    host = settings.get('mysql', 'host')
    user = settings.get('mysql', 'user')
    password = settings.get('mysql', 'pass')
    database = settings.get('mysql', 'database')
    port = settings.get('mysql', 'port')
    try:
        con = mysql.connector.connect(user=user, password=password, host=host, database=database, port=port)
        cur = con.cursor()
    except Exception as e:
        exception_handle(e)
    else:
        print('Zalogowano do mysql')
        return con, cur

def tmp_attachment_to_file(attachment):
    for name, bytes, _ in attachment:
        with open('attachments/'+name, 'bw') as f:
            f.write(bytes)

def mysql_close(con):
    con.close()

def gmail_close(gmail_con):
    gmail_con.quit()

def get_mailboxes(settings):
    boxes = [(k, v) for k, v in settings['boxes'].items()]
    return boxes

def get_mail_ids(box, last_id_done: int, quantity: int) -> list:
    '''calculates the list of mail ids to be imported'''
    ids_b = box.listids(quantity) # list of binary ids
    oldest_id = int(ids_b[-1])
    # since easyimap.listids gives fixed len list, not complete list, iterate to get the long enough list
    while not ((len(ids_b) < quantity) or (oldest_id < last_id_done) or (oldest_id == 1)): # all ids from the box collected
        quantity *= 10
        ids_b = box.listids(quantity)  # list of binary ids
        oldest_id = int(ids_b[-1])
    wynik = limit_id_list(last_id_done, ids_b)
    return wynik


def limit_id_list(last_id_done, id_list_b):
    '''limits list of ids to only larger than the last imported one'''
    id_list_b_new = [x for x in id_list_b if int(x)> last_id_done]
    return id_list_b_new

def process_datetime(mail_date):
    '''converse easyimap.date str to datetime removing the tz name or other info in the bracket at the end of the string'''
    try:
        datetime_obj = dateparser.parse(mail_date).astimezone()
    except AttributeError:
        mail_date = re.sub(' *\(.*\)$', '', mail_date)
        datetime_obj = dateparser.parse(mail_date).astimezone()
    return datetime_obj

def process_email(mailbox_name, m_id, box, con, cur, settings):
    '''gathers email attrs to be saved to mysql'''
    # global msg
    msg = box.mail(m_id)
    out = {}
    out['uid'] = int(m_id)
    out['mailbox'] = 'outbox' if mailbox_name == '[Gmail]/Wys&AUI-ane' else mailbox_name
    out['date'] = process_datetime(msg.date)
    out['from_addr'] = msg.from_addr
    out['to'] = msg.to
    out['cc'] = None if msg.cc == '' else msg.cc
    out['title'] = None if msg.title == '' else msg.title
    out['body'] = msg.body
    out['attachments'] = msg.attachments
    email_to_mysql(out, con, cur, settings)
    # save_email(out)
    # return out

def tmp_msg_print_body_len(mailbox_name, m_id, box, con, cur, settings):
    # global msg, data
    msg = box.mail(m_id)
    data.append((len(msg.body), m_id, mailbox_name))

def update_inbox_done(settings, inbox, mail_id):
    '''updates settings.ini with last imported mail id'''
    settings.set('boxes', inbox, mail_id)
    with open ('settings.ini', 'w') as f:
        settings.write(f)

def exception_handle(e: Exception):
    print('Klasa wyjątku:', type(e))
    print('Szczegóły wyjątku: ', e)
    print('Kończę')
    sys.exit()


def email_to_mysql(mail_dict, con, cur, settings):
    '''saves email data to mysql'''
    try:
        #transakcja
        con.start_transaction()

        #save to emails
        email_sql = """insert into mails (id, title, inbox, from_addr, to_addr, cc, date, body) values(%s, %s, %s, %s, %s, %s, %s, %s)"""
        email_values = (mail_dict['uid'], mail_dict['title'], mail_dict['mailbox'], mail_dict['from_addr'], mail_dict['to'],
                        mail_dict['cc'], mail_dict['date'], mail_dict['body'])
        cur.execute(email_sql, email_values)

        #save to attchmts
        for name, bytes, _ in mail_dict['attachments']:
            attachments_sql = """insert into attachments (file_name, file_content, mail_id, mail_inbox) values(%s, %s, %s, %s)"""
            attachments_values = (name, bytes, mail_dict['uid'], mail_dict['mailbox'])
            cur.execute(attachments_sql, attachments_values)
    except Exception as e:
        con.rollback()
        exception_handle(e)
    else:
        con.commit()
        update_inbox_done(settings, mail_dict['mailbox'], str(mail_dict['uid']))


def tmp_ave_email(msg_details: dict):
    with open('mails.txt', 'a', encoding='UTF') as f:
        # del msg_details['subject']
        for k, v in msg_details.items():
            f.write(f'{k}: {v}\n')



def process_emails(mailbox_name, id_list, box, con, cur, settings):
    # for m_id in [x for x in id_list if int(x) in (590,)]:
    list_len = len(id_list)
    print(f'Przetwarzam skrzynkę {mailbox_name}. Maili do importu: {list_len}')
    for i, m_id in enumerate(id_list[::-1]):
        if ((i % 100 == 0 and i > 0) or i == list_len): print(f'Zaimportowanych maili: {i}')
        # tmp_msg_print_body_len(mailbox_name, m_id, box, con, cur, settings)
        process_email(mailbox_name, m_id, box, con, cur, settings)


def main():
    # get settings
    settings = get_settings()
    # get mailboxes to process from settings with their last done email
    mailboxes = get_mailboxes(settings) #tupla (nazwa boxa, ostatni przetworzony id)
    for mailbox in mailboxes:
        # Actual name contains square brackets so can't be used in settings.ini, hence replacement
        if mailbox[0] == 'outbox':
            mailbox = ('[Gmail]/Wys&AUI-ane', mailbox[1])
        # mailbox name is the first element, second being last done email
        mailbox_name = mailbox[0]
        # connect to gmail; box points to current mailbox
        box = gmail_login(settings, mailbox_name)
        # calculate the list of mails to be imported
        mail_ids = get_mail_ids(box, int(mailbox[1]), 10)
        # connect to mysql
        mysql_con, mysql_cur = connect_mysql(settings)
        process_emails(mailbox_name, mail_ids, box, mysql_con, mysql_cur, settings)
        mysql_close(mysql_con)
        gmail_close(box)
    print('Koniec')

if __name__ == '__main__':
    main()
