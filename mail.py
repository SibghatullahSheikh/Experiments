from email.header import Header
from email.mime.text import MIMEText
from smtplib import SMTP_SSL
from types import ListType

from settings import *


def send_email(subject, message, to):
    outcome = True
    if type(to) is ListType:
        to = ', '.join(to)

    msg = MIMEText(message, _charset='utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = EMAIL_USER
    msg['To'] = to

    # send it via gmail
    s = SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=10)
    try:
        s.login(EMAIL_USER, EMAIL_PWD)
        s.sendmail(msg['From'], msg['To'], msg.as_string())
    except Exception, e:
        print "Error sending e-mail: %s" % e
        outcome = False

    s.quit()
    return outcome
