import os, json, sqlite3, datetime, io
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'change-me'

DB = 'data.sqlite'

TRANSLATIONS = {
  'ar': {
    'app_title':'نظام محاسبة المكتبة',
    'default_library':'مكتبتي',
    'arabic':'عربي', 'english':'إنكليزي', 'turkish':'تركي',
    'settings':'الإعدادات', 'footer_note':'© نظام محاسبة بسيط بالبايثون',
    'books_total':'عدد الكتب', 'invoices_total':'عدد الفواتير', 'stale_books':'كتب قديمة (6 أشهر+)',
    'manage_books':'إدارة الكتب', 'new_invoice':'فاتورة جديدة', 'view_stale':'عرض الكتب القديمة',
    'stale_alert':'تنبيه: لديك كتب مضى عليها 6 أشهر بدون بيع', 'stale_hint':'يمكنك عمل عروض عليها لتسريع البيع.',
    'books':'الكتب', 'add_book':'إضافة كتاب', 'title':'العنوان', 'author':'المؤلف', 'price':'السعر',
    'stock':'المخزون', 'last_sold':'آخر بيع', 'save':'حفظ',
    'customer_name':'اسم الزبون', 'phone':'الهاتف', 'book':'الكتاب', 'qty':'الكمية', 'add_item':'إضافة صنف',
    'create_invoice':'إنشاء فاتورة', 'invoice':'فاتورة', 'date':'التاريخ', 'total':'الإجمالي',
    'grand_total':'المجموع الكلي', 'download_pdf':'تنزيل PDF',
    'library_name':'اسم المكتبة', 'address':'العنوان', 'language':'اللغة', 'logo':'الشعار'
  },
  'en': {
    'app_title':'Bookstore Accounting',
    'default_library':'My Library',
    'arabic':'Arabic', 'english':'English', 'turkish':'Turkish',
    'settings':'Settings', 'footer_note':'© Simple Python Accounting',
    'books_total':'Books', 'invoices_total':'Invoices', 'stale_books':'Stale books (6+ months)',
    'manage_books':'Manage Books', 'new_invoice':'New Invoice', 'view_stale':'View Stale',
    'stale_alert':'Heads up: You have books older than 6 months unsold', 'stale_hint':'Consider promotions to move stock.',
    'books':'Books', 'add_book':'Add Book', 'title':'Title', 'author':'Author', 'price':'Price',
    'stock':'Stock', 'last_sold':'Last Sold', 'save':'Save',
    'customer_name':'Customer Name', 'phone':'Phone', 'book':'Book', 'qty':'Qty', 'add_item':'Add Item',
    'create_invoice':'Create Invoice', 'invoice':'Invoice', 'date':'Date', 'total':'Total',
    'grand_total':'Grand Total', 'download_pdf':'Download PDF',
    'library_name':'Library Name', 'address':'Address', 'language':'Language', 'logo':'Logo'
  },
  'tr': {
    'app_title':'Kitapçı Muhasebesi',
    'default_library':'Kütüphanem',
    'arabic':'Arapça', 'english':'İngilizce', 'turkish':'Türkçe',
    'settings':'Ayarlar', 'footer_note':'© Basit Python Muhasebe',
    'books_total':'Kitaplar', 'invoices_total':'Faturalar', 'stale_books':'Eski kitaplar (6+ ay)',
    'manage_books':'Kitapları Yönet', 'new_invoice':'Yeni Fatura', 'view_stale':'Eskileri Gör',
    'stale_alert':'6+ ay satılmayan kitaplar var', 'stale_hint':'Stok devri için promosyon yapın.',
    'books':'Kitaplar', 'add_book':'Kitap Ekle', 'title':'Başlık', 'author':'Yazar', 'price':'Fiyat',
    'stock':'Stok', 'last_sold':'Son Satış', 'save':'Kaydet',
    'customer_name':'Müşteri Adı', 'phone':'Telefon', 'book':'Kitap', 'qty':'Adet', 'add_item':'Satır Ekle',
    'create_invoice':'Fatura Oluştur', 'invoice':'Fatura', 'date':'Tarih', 'total':'Toplam',
    'grand_total':'Genel Toplam', 'download_pdf':'PDF İndir',
    'library_name':'Kütüphane Adı', 'address':'Adres', 'language':'Dil', 'logo':'Logo'
  }
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
    cur.execute('''CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, data TEXT)''')
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
    row = cur.fetchone()
    con.close()
    if row:
        return json.loads(row['data'])
    return {}

def save_settings(data):
    con = db(); cur = con.cursor()
    cur.execute('INSERT OR REPLACE INTO settings (id, data) VALUES (1, ?)', (json.dumps(data),))
    con.commit(); con.close()

@app.context_processor
def inject():
    return dict(t=t, settings=get_settings(), lang=get_lang())

def ensure_setup():
    st = get_settings()
    return not (st.get('library_name') or st.get('phone') or st.get('address'))

@app.route('/setup', methods=['GET','POST'])
def setup_wizard():
    if request.method == 'POST':
        st = {
            'library_name': request.form.get('library_name',''),
            'phone': request.form.get('phone',''),
            'address': request.form.get('address',''),
            'language': 'ar',
            'logo': ''
        }
        save_settings(st)
        return redirect(url_for('settings_page'))
    return render_template('settings.html')

@app.route('/lang/<code>')
def set_lang(code):
    session['lang'] = code if code in TRANSLATIONS else 'ar'
    flash('Language changed' if code!='ar' else 'تم تغيير اللغة')
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    if ensure_setup():
        return redirect(url_for('setup_wizard'))
    con = db(); cur = con.cursor()
    cur.execute('SELECT COUNT(*) AS c FROM books'); books = cur.fetchone()['c']
    cur.execute('SELECT COUNT(*) AS c FROM invoices'); invoices = cur.fetchone()['c']
    six_months_ago = (datetime.date.today() - datetime.timedelta(days=180)).isoformat()
    cur.execute('SELECT COUNT(*) AS c FROM books WHERE last_sold_at IS NULL OR last_sold_at < ?', (six_months_ago,))
    stale = cur.fetchone()['c']
    con.close()
    return render_template('index.html', counts={'books':books,'invoices':invoices}, stale_count=stale)

@app.route('/settings', methods=['GET','POST'])
def settings_page():
    st = get_settings()
    if request.method == 'POST':
        library_name = request.form.get('library_name','')
        phone = request.form.get('phone','')
        address = request.form.get('address','')
        language = request.form.get('language','ar')
        logo_path = st.get('logo','')
        file = request.files.get('logo')
        if file and file.filename:
            static_dir = os.path.join(app.root_path, 'static')
            os.makedirs(static_dir, exist_ok=True)
            logo_path = os.path.join('static', 'uploaded_logo.png')
            file.save(os.path.join(app.root_path, logo_path))
        st = {'library_name':library_name,'phone':phone,'address':address,'language':language,'logo':'/'+logo_path if logo_path else ''}
        save_settings(st)
        flash('Saved successfully' if language!='ar' else 'تم الحفظ بنجاح')
        return redirect(url_for('settings_page'))
    return render_template('settings.html')

@app.route('/books')
def books_list():
    con = db(); cur = con.cursor()
    cur.execute('SELECT * FROM books ORDER BY id DESC')
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return render_template('books.html', books=rows)

@app.route('/books/add', methods=['GET','POST'])
def book_add():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form.get('author','')
        sku = request.form.get('sku','')
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        con = db(); cur = con.cursor()
        cur.execute('INSERT INTO books (title,author,sku,price,stock,added_at) VALUES (?,?,?,?,?,?)',
                    (title,author,sku,price,stock, datetime.date.today().isoformat()))
        con.commit(); con.close()
        flash('تمت إضافة الكتاب' if get_lang()=='ar' else 'Book added')
        return redirect(url_for('books_list'))
    return render_template('book_add.html')

@app.route('/stale')
def stale_books():
    six_months_ago = (datetime.date.today() - datetime.timedelta(days=180)).isoformat()
    con = db(); cur = con.cursor()
    cur.execute('SELECT * FROM books WHERE last_sold_at IS NULL OR last_sold_at < ? ORDER BY last_sold_at', (six_months_ago,))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return render_template('books.html', books=rows)

@app.route('/invoices/new', methods=['GET','POST'])
def invoice_new():
    con = db(); cur = con.cursor()
    cur.execute('SELECT * FROM books ORDER BY title')
    books = [dict(r) for r in cur.fetchall()]
    if request.method == 'POST':
        ids = request.form.getlist('book_id')
        prices = request.form.getlist('price')
        qtys = request.form.getlist('qty')
        items = []
        total = 0.0
        for i in range(len(ids)):
            cur.execute('SELECT * FROM books WHERE id=?', (ids[i],))
            b = cur.fetchone()
            if not b: 
                continue
            price = float(prices[i])
            qty = int(qtys[i])
            items.append({'book_id': int(ids[i]), 'title': b['title'], 'price': price, 'qty': qty})
            total += price * qty
        customer_name = request.form.get('customer_name','')
        customer_phone = request.form.get('customer_phone','')
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        cur.execute('INSERT INTO invoices (date, customer_name, customer_phone, items_json, total) VALUES (?,?,?,?,?)',
                    (now, customer_name, customer_phone, json.dumps(items), total))
        inv_id = cur.lastrowid
        today = datetime.date.today().isoformat()
        for it in items:
            cur.execute('UPDATE books SET stock = stock - ?, total_sold = total_sold + ?, last_sold_at=? WHERE id=?',
                        (it['qty'], it['qty'], today, it['book_id']))
        con.commit(); con.close()
        return redirect(url_for('invoice_view', inv_id=inv_id))
    con.close()
    return render_template('invoice_new.html', books=books)

@app.route('/invoices/<int:inv_id>')
def invoice_view(inv_id):
    con = db(); cur = con.cursor()
    cur.execute('SELECT * FROM invoices WHERE id=?', (inv_id,))
    inv = cur.fetchone()
    con.close()
    if not inv:
        return "Not found", 404
    inv = dict(inv)
    inv['items'] = json.loads(inv['items_json'])
    return render_template('invoice_view.html', inv=inv)

@app.route('/invoices/<int:inv_id>/pdf')
def invoice_pdf(inv_id):
    con = db(); cur = con.cursor()
    cur.execute('SELECT * FROM invoices WHERE id=?', (inv_id,))
    inv = cur.fetchone()
    con.close()
    if not inv:
        return "Not found", 404
    inv = dict(inv); items = json.loads(inv['items_json'])
    st = get_settings()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    logo_fs = None
    logo_path = st.get('logo','')
    if logo_path and logo_path.startswith('/'):
        logo_fs = os.path.join(app.root_path, logo_path[1:])
    elif logo_path:
        logo_fs = os.path.join(app.root_path, logo_path)
    if logo_fs and os.path.exists(logo_fs):
        try:
            c.drawImage(logo_fs, 20*mm, (h-30*mm), width=20*mm, height=20*mm, preserveAspectRatio=True, mask='auto')
        except:
            pass

    c.setFont("Helvetica-Bold", 14)
    c.drawString(45*mm, h-20*mm, st.get('library_name','Library'))
    c.setFont("Helvetica", 10)
    c.drawString(45*mm, h-25*mm, f"{st.get('phone','')} • {st.get('address','')}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20*mm, h-40*mm, f"Invoice #{inv['id']}")
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, h-46*mm, f"Date: {inv['date']}")
    c.drawString(20*mm, h-52*mm, f"Customer: {inv.get('customer_name','')}  •  {inv.get('customer_phone','')}")

    y = h-65*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "Title")
    c.drawString(110*mm, y, "Price")
    c.drawString(130*mm, y, "Qty")
    c.drawString(150*mm, y, "Total")
    y -= 6*mm
    c.line(20*mm, y, 190*mm, y)
    y -= 6*mm

    c.setFont("Helvetica", 10)
    for it in items:
        if y < 30*mm:
            c.showPage()
            y = h - 20*mm
        c.drawString(20*mm, y, it['title'][:60])
        c.drawRightString(125*mm, y, f"{it['price']:.2f}")
        c.drawRightString(140*mm, y, str(it['qty']))
        c.drawRightString(190*mm, y, f"{(it['price']*it['qty']):.2f}")
        y -= 6*mm

    y -= 6*mm
    c.line(120*mm, y, 190*mm, y)
    y -= 8*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(190*mm, y, f"Grand Total: {inv['total']:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"invoice_{inv_id}.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    init_db()
    # For Render, PORT env var is provided
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
