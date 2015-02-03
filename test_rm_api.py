#! coding: utf-8
__author__ = 'Fedor'

import redmine


rm = redmine.Redmine('http://redmine.crypto.local', username='ofi', password='789789')
projects = rm.project.all()
proj_list = [proj for proj in projects]
member_list = {}
for proj in projects:
    #print('    ' + proj.name + '    ' + proj.identifier)
    memberships = rm.project_membership.filter(project_id=proj.identifier)
    #member_list[proj.name] = [member for member in memberships]
    for member in memberships:
        member_isManager = u'Chief Tester' in [role[u'name'] for role in member.roles.resources]
        if member_isManager:
            managers_mail = rm.user.get(member.user.id).mail
        #print(u'{member}    is manager: {isManager}').format(member=member.user.name, isManager=member_isManager)
print ('\n\n')
roles = rm.role.all()
role_list = [role for role in roles]
pass