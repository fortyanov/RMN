#! coding: utf-8
__author__ = 'Fedor Ortyanov'

import redmine
import json
import re
import os
import sys
from fabric.colors import *
from fabric.contrib.files import *
import datetime
import smtplib
from email.mime.text import MIMEText


if os.path.exists(os.path.join(os.path.dirname(__file__), 'settings.json')):
    #with cd(os.path.join(os.path.dirname(__file__))):
    settings_data = json.load(open('settings.json'))
    settings_priority = settings_data['prtiority']
else:
    print(red('Отсутствует файл с настройками settings.json'))
    sys.exit(1)

if os.path.exists(os.path.join(os.path.dirname(__file__), 'last_status.json')):  # содержит информацию о всех задачах
    all_issues = json.load(open('last_status.json'))
else:
    all_issues = {}

rm = redmine.Redmine('http://redmine.crypto.local', username='ofi', password='789789')   # подключаемся к redmine API
#redmine = Redmine('http://redmine', username='f.ortyanov', password='78907890')

admins_mail = 'redmine-tst@roscryptpro.ru'
redmine_url = 'redmine.crypto.local'
projects = rm.project.all()                 # rm means redmine object

try:
    send = smtplib.SMTP()                      # создаем подключение к почтовому серваку
    send.connect('172.20.1.5', 25)
    send.starttls()
    send.login('redmine-tst@roscryptpro.ru', '789789')
except Exception, e:
    print e
    print(red('Не удалось подключиться к почтовому серверу, обратитесь к администратору.'))
    sys.exit(1)

for proj in projects:
    print proj.name
    for issue in proj.issues:
        if not all_issues.get(issue.id):
            all_issues[issue.id] = {}
            all_issues[issue.id]['sended_to_responsible'] = False
            all_issues[issue.id]['sended_to_manager'] = False

        # СБОР НЕОБХОДИМЫХ ДЛЯ ОТПРАВКИ ДАННЫХ
        allotted_hours = int(settings_priority[issue.priority.name]['time'])
        used_td = datetime.datetime.now() - issue.created_on                      # _td - type(datetime.timedelta)
        used_hours = used_td.days * 8 + used_td.seconds / 3600                    # _hours - type(int) count of hours
        issue_link = os.path.join('http://', redmine_url, 'issues', str(issue.id))
        try:
            responsible_mail = rm.user.get(issue.assigned_to.id).mail
            responsible_name = issue.assigned_to.name
            #responsible_id = issue.assigned_to.id
        except:
            responsible_mail = rm.user.get(issue.author.id).mail
            responsible_name = issue.author.name
            #responsible_id = issue.author.id

        # ЗАЛИВКА ОСТАВШИХСЯ ДАННЫХ В ФАЙЛ МОНИТОРИНГА СОСТОЯНИЯ
        all_issues[issue.id]['responsible_name'] = responsible_name
        all_issues[issue.id]['responsible_mail'] = responsible_mail
        all_issues[issue.id]['used_hours'] = used_hours
        all_issues[issue.id]['allotted_hours'] = allotted_hours
        all_issues[issue.id]['subject'] = issue.subject

        # ОТПРАВКА СООБЩЕНИЯ ОТВЕТСТВЕННОМУ
        if allotted_hours >= used_hours >= allotted_hours * 0.75 and not all_issues[str(issue.id)]['sended_to_responsible']:
            res = u'{name}.\nУ вас осталось {hours} часов для завершения задачи "{subj}"\nN: {id}\nСсылка: {link}'\
                .format(name=responsible_name, hours=allotted_hours - used_hours, subj=issue.subject, id=issue.id, link=issue_link)
            print responsible_mail + '\n' + res
            msg = MIMEText(res, _charset='utf-8')
            msg['Subject'] = u'Необходимо закрыть задачу как можно скорее!'
            msg['From'] = admins_mail
            msg['To'] = responsible_mail
            send.sendmail(admins_mail, [responsible_mail], msg.as_string())
            all_issues[issue.id]['sended_to_responsible'] = True

        # ОТПРАВКА СООБЩЕНИЯ РУКОВОДИТЕЛЮ
        if allotted_hours - used_hours in (0, 1) and not all_issues[str(issue.id)]['sended_to_manager']:
            res = u'{name}.\nОсталось меньше часа для завершения задачи "{subj}"\nN: {id}\nСсылка: {link}\nЭто письмо будет автоматически направленно вашему руководителю.'\
                .format(name=responsible_name, hours=allotted_hours-used_hours, subj=issue.subject, id=issue.id, link=issue_link)
            print responsible_mail + '\n' + res
            msg = MIMEText(res, _charset='utf-8')
            msg['Subject'] = u'Для закрытия задачи осталось меньше часа!'
            msg['From'] = admins_mail
            msg['To'] = responsible_mail
            send.sendmail(admins_mail, [responsible_mail], msg.as_string())
            all_issues[issue.id]['sended_to_manager'] = True

open('last_status.json', 'wb').write(json.dumps(all_issues, indent=4))
send.quit()
