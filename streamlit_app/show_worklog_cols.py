import sqlite3
conn=sqlite3.connect('okr_database.db')
cursor=conn.cursor()
cursor.execute('PRAGMA table_info(work_log)')
cols=cursor.fetchall()
print('work_log columns:')
for c in cols:
    print(c)
conn.close()