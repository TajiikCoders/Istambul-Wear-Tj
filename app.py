# -*- coding: utf-8 -*-
import os
import uuid
import json
import random
import string
import threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime
import logging

# =====================================================================
# --- ҚИСМИ 0: ТАНЗИМОТИ АВВАЛИЯИ СЕРВЕР ---
# =====================================================================

# Эҷоди замимаи Flask
app = Flask(__name__)
# Иҷозат додани дархостҳо аз доменҳои дигар (муҳим барои frontend)
CORS(app)

# Хомӯш кардани логҳои стандартии дастрасии Flask барои тоза нигоҳ доштани консол
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Муайян кардани роҳҳои асосии лоиҳа
basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Агар папкаи 'uploads' вуҷуд надошта бошад, онро эҷод мекунем
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Роҳ ба файли асосии пойгоҳи додаҳо
DATABASE_FILE = os.path.join(basedir, 'database.json')

# +++ ИСЛОҲИ МУҲИМ: Қулф барои пойгоҳи додаҳо +++
# Ин қулф пеши роҳи хатогиҳоро мегирад, вақте ки якчанд корбар
# дар як вақт кӯшиши тағйир додани файлро мекунанд.
db_lock = threading.Lock()

# ---------------------------------------------------------------------
# Функсияҳои ёрирасон барои кор бо пойгоҳи додаҳо (файли JSON)
# ---------------------------------------------------------------------

def load_db():
    """
    Ин функсия маълумотро аз файли database.json мехонад.
    Агар файл вуҷуд надошта бошад ё холӣ бошад, сохтори холиро бармегардонад.
    """
    with db_lock:
        try:
            if os.path.exists(DATABASE_FILE) and os.path.getsize(DATABASE_FILE) > 0:
                with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass # Агар хатогӣ рух диҳад, сохтори холиро бармегардонем
    return {"users": [], "products": [], "orders": [], "reviews": [], "categories": [], "promo_codes": [], "subscribers": [], "stock_requests": [], "slides": []}

def save_db(data):
    """
    Ин функсия маълумоти додашударо дар файли database.json захира мекунад.
    Истифодаи 'with db_lock' амнияти маълумотро таъмин мекунад.
    """
    with db_lock:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

# =====================================================================
# --- ҚИСМИ 1: API Endpoints БАРОИ ВЕБСАЙТ (ҚИСМИ КОРБАР) ---
# =====================================================================

@app.route('/api/slides', methods=['GET'])
def get_slides():
    """Endpoint барои гирифтани рӯйхати слайдҳо барои саҳифаи асосӣ."""
    db = load_db()
    return jsonify(db.get('slides', []))

@app.route('/api/products', methods=['GET'])
def get_products():
    """Endpoint барои гирифтани рӯйхати ҳамаи маҳсулот."""
    return jsonify(load_db().get('products', []))

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Endpoint барои гирифтани маълумоти як маҳсулоти мушаххас аз рӯи ID."""
    product = next((p for p in load_db().get('products', []) if p.get('id') == product_id), None)
    if product:
        return jsonify(product)
    return jsonify({"error": "Маҳсулот ёфт нашуд"}), 404
    
@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Endpoint барои гирифтани рӯйхати ҳамаи категорияҳо."""
    return jsonify(load_db().get('categories', []))

@app.route('/api/orders', methods=['POST'])
def create_order():
    """
    Endpoint барои эҷоди фармоиши нав. Ин функсия ҳам фармоишҳоро аз вебсайт
    (ки андозаи интихобшуда доранд) ва ҳам аз бот (ки андоза надоранд) қабул мекунад.
    """
    data = request.get_json()
    if not data or 'cart' not in data:
        return jsonify({"error": "Дархости нодуруст"}), 400
        
    db = load_db()
    products, orders = db.get('products', []), db.get('orders', [])
    
    # Тафтиши мавҷудияти молҳо дар анбор
    for item in data.get('cart', []):
        product = next((p for p in products if p.get('id') == item.get('id')), None)
        if not product:
            return jsonify({"error": f"Маҳсулот бо ID {item.get('id')} ёфт нашуд."}), 400
        
        size_to_decrement = None
        item_quantity = item.get('quantity', 0)
        
        # 1. Агар андоза аз тарафи корбар интихоб шуда бошад (масалан, аз вебсайт)
        if 'selectedSize' in item and item['selectedSize']:
            size_inv = next((s for s in product.get('inventory', []) if s.get('size') == item['selectedSize']), None)
            if size_inv and size_inv.get('quantity', 0) >= item_quantity:
                size_to_decrement = size_inv
            else:
                 return jsonify({"error": f"Миқдори андозаи '{item['selectedSize']}' барои маҳсулоти '{product.get('name_tj')}' тамом шуд."}), 400
        
        # 2. Агар андоза интихоб нашуда бошад (фармоиш аз бот)
        else:
            for inv in product.get('inventory', []):
                if inv.get('quantity', 0) >= item_quantity:
                    size_to_decrement = inv
                    break
            if not size_to_decrement:
                return jsonify({"error": f"Миқдори маҳсулоти '{product.get('name_tj')}' дар анбор тамом шуд."}), 400

        # Миқдорро аз андозаи ёфтшуда кам мекунем
        size_to_decrement['quantity'] -= item_quantity

    new_order = {
        "id": str(uuid.uuid4()),
        "userId": data.get('userId'),
        "userName": data.get('userName', 'Номаълум'),
        "address": data.get('address'),
        "phone": data.get('phone'),
        "cart": data.get('cart', []),
        "total": data.get('total', 0),
        "promo_code": data.get('promoCode'),
        "status": "Нав",
        "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    orders.append(new_order)
    
    # Агар маблағи умумӣ аз 1100 сомонӣ зиёд бошад, промо-коди тӯҳфавӣ эҷод мекунем
    gift_promo_code = None
    if new_order['total'] > 1100:
        code = 'ORIYON-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        new_promo = {"id": str(uuid.uuid4()), "code": code, "discount": 10, "is_active": True}
        db.setdefault('promo_codes', []).append(new_promo)
        gift_promo_code = new_promo

    db.update({'orders': orders, 'products': products})
    save_db(db)
    
    response = {"message": "Фармоиши шумо бомуваффақият қабул карда шуд!", "gift_promo": gift_promo_code, "order_id": new_order['id']}
    return jsonify(response), 201

@app.route('/api/promo/apply', methods=['POST'])
def apply_promo_code():
    """Endpoint барои тафтиши дурустии промо-код."""
    data = request.get_json()
    code, user_id = data.get('code'), data.get('userId')
    if not code or not user_id: return jsonify({"error": "Промо-код ва ID-и корбар лозим аст"}), 400
    db = load_db()
    promo = next((p for p in db.get('promo_codes', []) if p.get('code', '').upper() == code.upper()), None)
    if not promo: return jsonify({"error": "Промо-код нодуруст аст"}), 404
    if not promo.get('is_active', False): return jsonify({"error": "Муҳлати истифодаи ин промо-код гузаштааст"}), 400
    if any(o.get('userId') == user_id and o.get('promo_code') == code for o in db.get('orders', [])):
        return jsonify({"error": "Шумо аллакай ин промо-кодро истифода бурдаед"}), 400
    return jsonify(promo)

@app.route('/api/register', methods=['POST'])
def register():
    """Endpoint барои бақайдгирии корбари нав."""
    data = request.get_json()
    db = load_db()
    users = db.get('users', [])
    if any(u['email'] == data['email'] for u in users):
        return jsonify({"error": "Ин почтаи электронӣ аллакай ба қайд гирифта шудааст"}), 400
    new_user = {"id": str(uuid.uuid4()), "name": data['name'], "email": data['email'], "password": data['password'], "role": "customer"}
    users.append(new_user)
    db['users'] = users
    save_db(db)
    return jsonify({"message": "Шумо бомуваффақият сабти ном шудед", "token": new_user['id'], "name": new_user['name']}), 201

@app.route('/api/login', methods=['POST'])
def login():
    """Endpoint барои воридшавии корбар ба система."""
    data = request.get_json()
    user = next((u for u in load_db().get('users', []) if u['email'] == data['email'] and u['password'] == data['password']), None)
    if user:
        return jsonify({"message": "Хуш омадед!", "token": user['id'], "name": user['name']})
    return jsonify({"error": "Почтаи электронӣ ё рамз нодуруст аст"}), 401
    
@app.route('/api/reviews/<int:product_id>', methods=['GET'])
def get_reviews(product_id):
    """Endpoint барои гирифтани шарҳҳо барои як маҳсулоти мушаххас."""
    return jsonify([r for r in load_db().get('reviews', []) if r.get('productId') == str(product_id)])

@app.route('/api/reviews', methods=['POST'])
def add_review():
    """Endpoint барои илова кардани шарҳи нав."""
    data = request.get_json()
    db = load_db()
    user = next((u for u in db.get('users', []) if u['id'] == data['userId']), None)
    if not user: return jsonify({"error": "Корбар ёфт нашуд"}), 404
    new_review = {"id": str(uuid.uuid4()), "productId": data['productId'], "userId": data['userId'], "userName": user['name'], "rating": int(data['rating']), "comment": data['comment'], "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    db.setdefault('reviews', []).append(new_review)
    save_db(db)
    return jsonify({"message": "Ташаккур барои шарҳи шумо!"}), 201
    
@app.route('/api/user/orders', methods=['GET'])
def get_user_orders():
    """Endpoint барои гирифтани таърихи фармоишҳои як корбар."""
    user_id = request.args.get('userId')
    if not user_id: return jsonify({"error": "ID-и корбар лозим аст"}), 400
    user_orders = [o for o in load_db().get('orders', []) if o.get('userId') == user_id]
    return jsonify(sorted(user_orders, key=lambda o: o['createdAt'], reverse=True))

@app.route('/api/stock_request', methods=['POST'])
def stock_request():
    """Endpoint барои қабули дархост барои маҳсулоти тамомшуда."""
    data = request.get_json()
    db = load_db()
    user = next((u for u in db.get('users', []) if u['id'] == data['userId']), None)
    product = next((p for p in db.get('products', []) if p['id'] == int(data['productId'])), None)
    if not user or not product: return jsonify({"error": "Корбар ё маҳсулот ёфт нашуд"}), 404
    new_request = {"id": str(uuid.uuid4()), "userId": data['userId'], "userName": user['name'], "productId": data['productId'], "productName": product['name'], "size": data['size'], "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    db.setdefault('stock_requests', []).append(new_request)
    save_db(db)
    return jsonify({"message": "Дархости шумо қабул шуд! Мо ба шумо хабар медиҳем."})

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    """Endpoint барои обуна шудан ба хабарнома."""
    email = request.json.get('email')
    if not email: return jsonify({"error": "Почтаи электронӣ лозим аст"}), 400
    db = load_db()
    subscribers = db.get('subscribers', [])
    if email in [s.get('email') for s in subscribers]: return jsonify({"error": "Ин почта аллакай обуна шудааст"}), 400
    subscribers.append({"id": str(uuid.uuid4()), "email": email, "subscribed_at": datetime.now().strftime("%Y-%m-%d")})
    db['subscribers'] = subscribers
    save_db(db)
    return jsonify({"message": "Ташаккур барои обуна шудан!"}), 201

# =====================================================================
# --- ҚИСМИ 2: API Endpoints БАРОИ ПАНЕЛИ АДМИНИСТРАТОР ---
# =====================================================================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Endpoint барои воридшавии администратор."""
    data = request.get_json()
    admin = next((u for u in load_db().get('users', []) if u.get('email', '').lower() == data.get('email', '').lower() and u.get('password') == data.get('password') and u.get('role') == 'admin'), None)
    if admin:
        return jsonify({"message": "Хуш омадед, Администратор!"})
    return jsonify({"error": "Номи корбар ё рамз нодуруст аст"}), 401

@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """Endpoint барои гирифтани омори умумӣ барои админ."""
    db = load_db()
    orders = db.get('orders', [])
    users = db.get('users', [])
    products = db.get('products', [])
    stats = {
        "total_revenue": sum(o.get('total', 0) for o in orders if o.get('status') == 'Иҷро шуд'),
        "new_orders": sum(1 for o in orders if o.get('status') == 'Нав'),
        "total_orders": len(orders),
        "total_customers": sum(1 for u in users if u.get('role') == 'customer'),
        "total_products": len(products)
    }
    return jsonify(stats)

@app.route('/api/admin/slides', methods=['GET', 'POST'])
def manage_slides():
    """Endpoint барои идоракунии слайдҳо (гирифтан ва илова кардан)."""
    db = load_db()
    slides = db.get('slides', [])
    if request.method == 'GET':
        return jsonify(slides)
    if request.method == 'POST':
        if 'image' not in request.files: return jsonify({"error": "Акс ёфт нашуд"}), 400
        file = request.files['image']
        filename = f"{uuid.uuid4()}_{os.path.basename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_slide = {"id": str(uuid.uuid4()), "title": request.form['title'], "subtitle": request.form['subtitle'], "image": f'/static/uploads/{filename}'}
        slides.append(new_slide)
        db['slides'] = slides
        save_db(db)
        return jsonify(new_slide), 201

@app.route('/api/admin/slides/<string:slide_id>', methods=['DELETE'])
def delete_slide(slide_id):
    """Endpoint барои нест кардани слайд."""
    db = load_db()
    slides = db.get('slides', [])
    slide_to_delete = next((s for s in slides if s['id'] == slide_id), None)
    if not slide_to_delete: return jsonify({"error": "Слайд ёфт нашуд"}), 404
    # Нест кардани файли акс аз диск
    img_path = os.path.join(basedir, slide_to_delete.get('image', '').lstrip('/'))
    if os.path.exists(img_path): os.remove(img_path)
    slides = [s for s in slides if s['id'] != slide_id]
    db['slides'] = slides
    save_db(db)
    return jsonify({"message": "Слайд бомуваффақият нест карда шуд"})

@app.route('/api/admin/orders', methods=['GET'])
def get_all_orders():
    """Endpoint барои гирифтани рӯйхати ҳамаи фармоишҳо барои админ."""
    all_orders = load_db().get('orders', [])
    return jsonify(sorted(all_orders, key=lambda o: o['createdAt'], reverse=True))

@app.route('/api/admin/orders/<string:order_id>', methods=['PUT', 'DELETE'])
def manage_order(order_id):
    """Endpoint барои тағйир додани статуси фармоиш ё нест кардани он."""
    db = load_db()
    orders = db.get('orders', [])
    idx = next((i for i, o in enumerate(orders) if o['id'] == order_id), None)
    if idx is None: return jsonify({"error": "Фармоиш ёфт нашуд"}), 404
    if request.method == 'PUT':
        orders[idx]['status'] = request.json.get('status', orders[idx]['status'])
    elif request.method == 'DELETE':
        orders.pop(idx)
    db['orders'] = orders
    save_db(db)
    return jsonify({"message": "Амалиёт бомуваффақият иҷро шуд"})

@app.route('/api/admin/products', methods=['POST'])
def add_product():
    """Endpoint барои илова кардани маҳсулоти нав."""
    if 'image' not in request.files: return jsonify({"error": "Акс ёфт нашуд"}), 400
    file = request.files['image']
    if not file.filename: return jsonify({"error": "Файли интихобшуда ном надорад"}), 400
    filename = f"{uuid.uuid4()}_{os.path.basename(file.filename)}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    db = load_db()
    products = db.get('products', [])
    new_product = {
        "id": (products[-1]['id'] + 1) if products else 1,
        "name_tj": request.form.get('name_tj') or request.form.get('name'),
        "name_ru": request.form.get('name_ru') or request.form.get('name'),
        "name_en": request.form.get('name_en') or request.form.get('name'),
        "description_tj": request.form.get('description_tj') or request.form.get('description'),
        "description_ru": request.form.get('description_ru') or request.form.get('description'),
        "description_en": request.form.get('description_en') or request.form.get('description'),
        "price": float(request.form['price']),
        "category": request.form['category'],
        "image": f'/static/uploads/{filename}', 
        "inventory": json.loads(request.form['inventory'])
    }
    products.append(new_product)
    db['products'] = products
    save_db(db)
    return jsonify(new_product), 201

@app.route('/api/admin/products/<int:product_id>', methods=['PUT', 'DELETE'])
def manage_product(product_id):
    """Endpoint барои таҳрир кардан ё нест кардани маҳсулот."""
    db = load_db()
    products = db.get('products', [])
    idx = next((i for i, p in enumerate(products) if p['id'] == product_id), None)
    if idx is None: return jsonify({"error": "Маҳсулот ёфт нашуд"}), 404
    if request.method == 'DELETE':
        img_path = os.path.join(basedir, products[idx].get('image', '').lstrip('/'))
        if os.path.exists(img_path): os.remove(img_path)
        products.pop(idx)
    elif request.method == 'PUT':
        product = products[idx]
        product.update({k: request.form.get(k, v) for k, v in product.items()})
        product['price'] = float(request.form.get('price', product['price']))
        product['inventory'] = json.loads(request.form.get('inventory', json.dumps(product.get('inventory', []))))
        if 'image' in request.files and request.files['image'].filename:
            old_img = os.path.join(basedir, product.get('image', '').lstrip('/'))
            if os.path.exists(old_img): os.remove(old_img)
            file = request.files['image']
            filename = f"{uuid.uuid4()}_{os.path.basename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            product['image'] = f'/static/uploads/{filename}'
        products[idx] = product
    db['products'] = products
    save_db(db)
    return jsonify(products[idx] if request.method == 'PUT' else {"message": "Маҳсулот нест карда шуд"})

@app.route('/api/admin/categories', methods=['GET', 'POST'])
def manage_categories():
    """Endpoint барои идоракунии категорияҳо (гирифтан ва илова кардан)."""
    db = load_db()
    categories = db.get('categories', [])
    if request.method == 'GET': return jsonify(categories)
    if request.method == 'POST':
        name = request.json['name']
        if any(c.get('name_tj', '').lower() == name.lower() for c in categories):
            return jsonify({"error": "Категория бо чунин ном аллакай вуҷуд дорад"}), 400
        new_category = {"id": str(uuid.uuid4()), "name_tj": name, "name_ru": name, "name_en": name}
        categories.append(new_category)
        db['categories'] = categories
        save_db(db)
        return jsonify(new_category), 201

@app.route('/api/admin/categories/<string:category_id>', methods=['PUT', 'DELETE'])
def manage_category(category_id):
    """Endpoint барои таҳрир кардан ё нест кардани категория."""
    db = load_db()
    categories = db.get('categories', [])
    idx = next((i for i, c in enumerate(categories) if c['id'] == category_id), None)
    if idx is None: return jsonify({"error": "Категория ёфт нашуд"}), 404
    if request.method == 'DELETE': categories.pop(idx)
    elif request.method == 'PUT':
        name = request.json.get('name')
        categories[idx].update({"name_tj": name, "name_ru": name, "name_en": name})
    db['categories'] = categories
    save_db(db)
    return jsonify(categories[idx] if request.method == 'PUT' else {"message": "Категория нест карда шуд"})

# =====================================================================
# --- ҚИСМИ 3: API Endpoints БАРОИ БОТИ ТЕЛЕГРАМ ---
# =====================================================================

@app.route('/api/bot/categories', methods=['GET'])
def get_bot_categories():
    """Endpoint махсус барои бот, барои гирифтани категорияҳо."""
    db = load_db()
    return jsonify(db.get('categories', []))

@app.route('/api/bot/products', methods=['GET'])
def get_bot_products():
    """
    Endpoint махсус барои бот, барои гирифтани маҳсулот.
    Ин функсия URL-и пурраи аксро эҷод мекунад, то бот онро нишон дода тавонад.
    """
    db = load_db()
    category_id = request.args.get('category_id')
    
    # +++ ИСЛОҲИ МУҲИМ: Суроғаи динамикӣ +++
    # Суроғаи асосиро аз тағирёбандаҳои муҳити система мегирем.
    # Агар он вуҷуд надошта бошад (масалан, ҳангоми тест дар компютер),
    # суроғаи маҳаллии "http://127.0.0.1:5000"-ро истифода мебарем.
    base_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000")

    all_products = db.get('products', [])
    
    if category_id:
        category = next((c for c in db.get('categories', []) if c.get('id') == category_id), None)
        if category:
            # Маҳсулотро аз рӯи номи категорияи тоҷикӣ филтр мекунем
            products_in_category = [p for p in all_products if p.get('category') == category.get('name_tj')]
        else:
            products_in_category = []
    else:
        products_in_category = all_products

    # Барои ҳар як маҳсулот URL-и пурраи аксро илова мекунем
    for p in products_in_category:
        if p.get('image', '').startswith('/static'):
            p['image_url'] = f"{base_url}{p['image']}"
            
    return jsonify(products_in_category)
    
# =====================================================================
# --- ҚИСМИ 4: ФУНКСИЯҲОИ УМУМӢ ВА ОҒОЗИ СЕРВЕР ---
# =====================================================================

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Ин роут барои дастрас кардани файлҳои боршуда (аксҳо) аз браузер хизмат мекунад."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Ин қисм танҳо вақте иҷро мешавад, ки файл мустақиман ба кор дароварда шавад
    print("*" * 50)
    print("Сервери Flask дар http://127.0.0.1:5000 фаъол аст...")
    print("Барои қатъ кардан, CTRL+C -ро пахш кунед.")
    print("*" * 50)
    # debug=False барои муҳити продакшн муҳим аст
    app.run(host='0.0.0.0', port=5000, debug=False)
