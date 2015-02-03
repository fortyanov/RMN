#! coding: utf-8
#!/usr/bin/python

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

class RedmineMailSender(object):
    def __init__(self, **kwargs):
        """
        Инициализация полей
        """
        if os.path.exists(os.path.join(os.path.dirname(__file__), 'settings.json')):
            settings_data = json.load(open('settings.json'))
            self.settings_priority = settings_data['priority']
            self.managers_role = settings_data['managers_role']
            connection_data = settings_data['connection']
        else:
            print(red('Отсутствует файл с настройками settings.json'))
            sys.exit(1)

        self.rm_user = kwargs.get('rm_user', connection_data['rm_user'])                 # rm_ redmine
        self.rm_pass = kwargs.get('rm_pass', connection_data['rm_pass'])
        self.ms_user = kwargs.get('ms_user', str(connection_data['ms_user']))            # ms_ mail server
        self.ms_pass = kwargs.get('ms_pass', str(connection_data['ms_pass']))
        self.ms_addr = kwargs.get('ms_addr', str(connection_data['ms_addr']))
        self.rm_url = kwargs.get('rm_url', connection_data['rm_url'])

        self.preparation()


    def preparation(self):
        """
        Устанавливает все подключения и создает объекты для взоимодействия с API различных систем
        """
        if os.path.exists(os.path.join(os.path.dirname(__file__), 'last_status.json')):  # логи
            self.all_issues = json.load(open('last_status.json'))['all_issues']
        else:
            self.all_issues = {}

        self.rm = redmine.Redmine(('http://' + self.rm_url), username=self.rm_user, password=self.rm_pass)   # подключаемся к redmine API

        try:
            self.send = smtplib.SMTP()                      # создаем подключение к почтовому серваку
            self.send.connect(self.ms_addr, 25)
            self.send.starttls()
            self.send.login(self.ms_user, self.ms_pass)
        except Exception, e:
            print e
            print(red('Не удалось подключиться к почтовому серверу, обратитесь к администратору.'))
            sys.exit(2)


    def collect_issue_data(self, issue):
        """
        Собирает необходимые данные о конкретной задаче и возвращает в виде словаря
        """
        allotted_hours = int(self.settings_priority[issue.priority.name])
        used_td = datetime.datetime.now() - issue.created_on                      # _td - type(datetime.timedelta)
        used_hours = used_td.days * 8 + used_td.seconds / 3600                    # _hours - type(int) count of hours
        issue_link = os.path.join('http://', self.rm_url, 'issues', str(issue.id))
        issue_id = issue.id
        try:
            responsible_mail = self.rm.user.get(issue.assigned_to.id).mail
            responsible_name = issue.assigned_to.name
        except:
            responsible_mail = self.rm.user.get(issue.author.id).mail
            responsible_name = issue.author.name

        issue_data = {'responsible_name': responsible_name, 'responsible_mail': responsible_mail,
                      'used_hours': used_hours, 'allotted_hours': allotted_hours, 'subject': issue.subject,
                      'issue_link': issue_link, 'issue_id': issue_id}
        return issue_data


    def send_toResponsible(self, issue_data):
        """
        Отправляет сообщение ответственному
        """
        res = u'{name}.\nУ вас осталось {hours} часов для завершения задачи "{subj}"\nN: {id}\nСсылка: {link}'\
        .format(name=issue_data['responsible_name'], hours=issue_data['allotted_hours'] - issue_data['used_hours'],
                subj=issue_data['subject'], id=issue_data['issue_id'], link=issue_data['issue_link'])
        print(issue_data['responsible_mail'] + '\n' + res)
        msg = MIMEText(res, _charset='utf-8')
        msg['Subject'] = u'Необходимо закрыть задачу как можно скорее!'
        msg['From'] = self.ms_user
        msg['To'] = issue_data['responsible_mail']
        self.send.sendmail(self.ms_user, [issue_data['responsible_mail']], msg.as_string())
        self.all_issues[str(issue_data['issue_id'])]['sended_to_responsible'] = True


    def send_toManager(self, issue_data, managers_mail):
        """
        Отправляет сообщение руководителю и ответственному
        """
        res = u'{name}.\nОсталось меньше часа для завершения задачи "{subj}"\nN: {id}\nСсылка: {link}\nЭто письмо будет автоматически направленно вашему руководителю.'\
        .format(name=issue_data['responsible_name'], hours=issue_data['allotted_hours'] - issue_data['used_hours'],
                subj=issue_data['subject'], id=issue_data['issue_id'], link=issue_data['issue_link'])
        print(issue_data['responsible_mail'] + '\n' + res)
        msg = MIMEText(res, _charset='utf-8')
        msg['Subject'] = u'Для закрытия задачи осталось меньше часа!'
        msg['From'] = self.ms_user
        msg['To'] = issue_data['responsible_mail']
        delivery_list = [issue_data['responsible_mail']]
        delivery_list.extend(managers_mail)
        self.send.sendmail(self.ms_user, delivery_list, msg.as_string())
        self.all_issues[str(issue_data['issue_id'])]['sended_to_manager'] = True


    def get_managers_mail(self, proj, managers_role):
        """
        Возврашает почтовые адреса руководителей проекта
        """
        managers_mail = []
        memberships = self.rm.project_membership.filter(project_id=proj.identifier)
        for member in memberships:
            member_isManager = managers_role in [role[u'name'] for role in member.roles.resources]
            if member_isManager:
                managers_mail.append(self.rm.user.get(member.user.id).mail)
                return managers_mail


    def start(self):
        """
        Пробегает по проектам, при опр. events выполняет рассылку и записывает данные в файл
        """
        projects = self.rm.project.all()
        for proj in projects:
            print(proj.name)
            for issue in proj.issues:
                if not self.all_issues.get(str(issue.id)):
                    self.all_issues[str(issue.id)] = {'sended_to_responsible': False, 'sended_to_manager': False}
                self.all_issues[str(issue.id)].update(self.collect_issue_data(issue))

                send_toResponsible_event = self.all_issues[str(issue.id)]['allotted_hours'] \
                                           >= self.all_issues[str(issue.id)]['used_hours'] \
                                           >= self.all_issues[str(issue.id)]['allotted_hours'] * 0.75 \
                                           and not self.all_issues[str(issue.id)]['sended_to_responsible']

                send_toManager_event = (self.all_issues[str(issue.id)]['allotted_hours'] -
                                        self.all_issues[str(issue.id)]['used_hours']) in (0, 1) \
                                        and not self.all_issues[str(issue.id)]['sended_to_manager']

                if send_toResponsible_event:
                    self.send_toResponsible(self.all_issues[str(issue.id)])

                if send_toManager_event:
                    managers_mail = self.get_managers_mail(proj=proj, managers_role=self.managers_role)
                    self.send_toManager(self.all_issues[str(issue.id)], managers_mail)

        os.system('sudo touch last_status.json')
        os.system('sudo chmod 777 last_status.json')
        with open('last_status.json', 'wb') as status:
            status.seek(0)
            timestamp = datetime.datetime.now().strftime("%d.%m.%Y %I:%M %p")
            result = {'timestamp': timestamp, 'all_issues': self.all_issues}
            status.write(json.dumps(result, ensure_ascii=False, encoding='utf8', indent=4).encode("utf8"))
        self.send.quit()

if __name__ == '__main__':
    RedmineMailSender().start()
