f = 'backend/api/routers/alerts.py'
with open(f, 'rb') as fh:
    data = fh.read()

old = b"            enabled=True,\n            cooldown_seconds=0,"
new = b"            active=True,\n            cooldown_hours=0,"
if old in data:
    data = data.replace(old, new, 1)
    print('OK: fixed enabled/cooldown_seconds')
else:
    print('NOT FOUND')
    # try to find similar
    import re
    m = re.search(rb'enabled=.+|cooldown_seconds', data)
    if m:
        print('Found similar at byte', m.start(), repr(data[m.start():m.start()+30]))

# also fix: remove status='active' from Alert creation
old2 = b"        message='[TEST] This is a synthetic test alert from GlobalIntelligence.',\n        status='active',"
new2 = b"        message='[TEST] This is a synthetic test alert from GlobalIntelligence.',"
if old2 in data:
    data = data.replace(old2, new2, 1)
    print('OK: removed status from Alert')
else:
    print('NOT FOUND: status removal')
    # try to find
    idx = data.find(b"status='active'")
    if idx >= 0:
        print('Found status=active at byte', idx, repr(data[idx-50:idx+30]))

with open(f, 'wb') as fh:
    fh.write(data)
print('done')
