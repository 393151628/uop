#!/usr/bin/python
# -*- coding: UTF-8 -*-

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import parseaddr, formataddr
from uop.log import Log
email_server = 'casarray.syswin.com'
sender = 'zhanghai@syswin.com'
subjects = {
    '100': u'创建虚机资源成功',
    '200': u'申请虚机资源成功',
    '300': u'资源到期提醒'
}


def _format_addr(s):
    name, addr = parseaddr(s)
    return formataddr(
        (
            Header(name, 'utf-8').encode(),
            addr.encode('utf-8') if isinstance(addr, unicode) else addr
        )
    )


class SendEmail(object):

    def __init__(self, username, content, email_address, cc_email_address, subject_type):
        self.email_server = email_server
        self.username = username
        self.content = content
        self.email_address = email_address
        self.cc_email_address = cc_email_address
        self.sender = sender
        self.subjects = subjects
        self.subject = self.subjects.get(subject_type)

    def send_email(self):
        Log.logger.info("55555555555555555555555555555555555555555555555555")
        message = MIMEText(
            '%s' %
            self.content, 'plain', 'utf-8'
        )
        message['From'] = _format_addr(u"UOP <%s>" % self.sender)
        message['Subject'] = Header(self.subject, 'utf-8')
        try:
            Log.logger.info("6666666666666666666666666666666666666666666666666666")
            smtpObj = smtplib.SMTP(self.email_server)
            message['To'] = ";".join(self.email_address)
            message['Cc'] = ";".join(self.cc_email_address)
            smtpObj.sendmail(
                self.sender, self.email_address + self.cc_email_address, message.as_string()
            )
            Log.logger.info("[EMAIL] Send email successful.")
            res = True
        except Exception as e:
            Log.logger.info.exception(
                "[EMAIL] Send email faild. Exception: %s", str(e)
            )
            res = False
        return res


if __name__ == '__main__':

    send = SendEmail(
        username='victor',
        content='create virtual machine successful.',
        email_address=['yangyang@syswin.com'],
        cc_email_address=['fengyukai@syswin.com'],
        subject_type='100'
    )
    send.send_email()
