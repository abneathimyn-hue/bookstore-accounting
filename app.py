import os, json, sqlite3, datetime, io
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'change-me'

DB = 'data.sqlite'

# === Translations (cut short for brevity) ===
TRANSLATIONS = {
  'ar': {'app_title':'نظام محاسبة المكتبة', 'default_library':'مكتبتي'},
  'en': {'app_title':'Bookstore Accounting', 'default_library':'My Library'},
  'tr': {'app_title':'Kitapçı Muhasebesi', 'default_library':'Kütüphanem'},
}

def t(key):
    lang = get_lang()
    return TRANSLATIONS.get(lang, TRANSLATIONS['ar']).get(key, key)

def get_lang():
    if 'lang' in session:
        return session['lang']
    st = get_settings()
    return st.get('language','ar') if st else 'ar'

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, data TEXT)')
    cur.execute('''CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, author TEXT, sku TEXT, price REAL, stock INTEGER,
        added_at TEXT, last_sold_at TEXT, total_sold INTEGER DEFAULT 0
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, customer_name TEXT, customer_phone TEXT, items_json TEXT, total REAL
    )''')
    con.commit(); con.close()

def get_settings():
    con = db(); cur = con.cursor()
    cur.execute('SELECT data FROM settings WHERE id=1')
    row = cur.fetchone(); con.close()
    if row: return json.loads(row['data'])
    return {}

def save_settings(data):
    con = db(); cur = con.cursor()
    cur.execute('INSERT OR REPLACE INTO settings (id, data) VALUES (1, ?)', (json.dumps(data),))
    con.commit(); con.close()

@app.context_processor
def inject():
    return dict(t=t, settings=get_settings(), lang=get_lang())

@app.route('/')
def index():
    con = db(); cur = con.cursor()
    cur.execute('SELECT COUNT(*) AS c FROM books'); books = cur.fetchone()['c']
    cur.execute('SELECT COUNT(*) AS c FROM invoices'); invoices = cur.fetchone()['c']
    six_months_ago = (datetime.date.today() - datetime.timedelta(days=180)).isoformat()
    cur.execute('SELECT COUNT(*) AS c FROM books WHERE last_sold_at IS NULL OR last_sold_at < ?', (six_months_ago,))
    stale = cur.fetchone()['c']; con.close()
    return f"System Ready ✅ Books: {books}, Invoices: {invoices}, Old Books: {stale}"

# ✅ Always ensure DB is initialized (works on Render gunicorn too)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
