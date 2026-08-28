import sqlite3
conn = sqlite3.connect('outputs/relations.db')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM articles')
print('文章總數:', cur.fetchone())
cur.execute('SELECT dyad, language, COUNT(*) FROM articles GROUP BY dyad, language ORDER BY dyad, language')
for row in cur.fetchall():
    print(row)
conn.close()