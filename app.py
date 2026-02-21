"""
ДомашнийУют — Сайт сети магазинов товаров для дома
Разработан на Flask + SQLite
Соответствует требованиям ГОСТ 34.602-2020
"""

import os
import re
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

# ============================================================
# КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ
# ============================================================

app = Flask(__name__)

# Секретный ключ сессий (только ASCII — требование Flask-Login / latin-1 кодировка)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'domashni-uyt-flask-secret-key-2026')

# Настройка URI базы данных
# Render.com передаёт DATABASE_URL для PostgreSQL, по умолчанию — SQLite
_db_url = os.environ.get('DATABASE_URL', 'sqlite:///homegoods.db')
if _db_url.startswith('postgres://'):          # Render использует устаревший postgres://
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений Flask
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для доступа к этой странице необходимо войти.'
login_manager.login_message_category = 'warning'


# ============================================================
# МОДЕЛИ БАЗЫ ДАННЫХ
# ============================================================

class User(UserMixin, db.Model):
    """Модель пользователя.
    Роли: admin — администратор, manager — менеджер, user — покупатель.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name  = db.Column(db.String(200))
    phone      = db.Column(db.String(20))
    role       = db.Column(db.String(20), default='user', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active  = db.Column(db.Boolean, default=True)

    # Связи
    messages = db.relationship('Message', backref='author', lazy=True,
                               foreign_keys='Message.user_id')
    articles = db.relationship('NewsArticle', backref='author', lazy=True)

    def set_password(self, password: str) -> None:
        """Хеширует и сохраняет пароль."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Проверяет соответствие пароля хешу."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        """Возвращает True, если пользователь — администратор."""
        return self.role == 'admin'

    def is_manager(self) -> bool:
        """Возвращает True, если пользователь — менеджер или администратор."""
        return self.role in ('admin', 'manager')

    def __repr__(self):
        return f'<User {self.username} [{self.role}]>'


class Category(db.Model):
    """Категория товаров."""
    __tablename__ = 'categories'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    slug        = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon        = db.Column(db.String(50), default='bi-box')
    order       = db.Column(db.Integer, default=0)

    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    """Модель товара."""
    __tablename__ = 'products'

    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(200), nullable=False)
    slug             = db.Column(db.String(200), unique=True, nullable=False)
    category_id      = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    price            = db.Column(db.Float, nullable=False)
    old_price        = db.Column(db.Float)
    description      = db.Column(db.Text)
    full_description = db.Column(db.Text)
    image            = db.Column(db.String(255))
    is_featured      = db.Column(db.Boolean, default=False)   # Рекомендуем
    is_new           = db.Column(db.Boolean, default=False)   # Новинка
    is_sale          = db.Column(db.Boolean, default=False)   # Скидка
    stock            = db.Column(db.Integer, default=100)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def discount_percent(self) -> int:
        """Вычисляет процент скидки относительно старой цены."""
        if self.old_price and self.old_price > self.price:
            return int((1 - self.price / self.old_price) * 100)
        return 0

    def __repr__(self):
        return f'<Product {self.name}>'


class NewsArticle(db.Model):
    """Новостная статья / статья блога."""
    __tablename__ = 'news'

    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(300), nullable=False)
    slug         = db.Column(db.String(300), unique=True, nullable=False)
    preview      = db.Column(db.Text)
    content      = db.Column(db.Text, nullable=False)
    author_id    = db.Column(db.Integer, db.ForeignKey('users.id'))
    category     = db.Column(db.String(100), default='Новости')
    image        = db.Column(db.String(255))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    views        = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<NewsArticle {self.title}>'


class Banner(db.Model):
    """Баннер главного слайдера."""
    __tablename__ = 'banners'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200))
    subtitle    = db.Column(db.String(300))
    image       = db.Column(db.String(255))
    link        = db.Column(db.String(255))
    button_text = db.Column(db.String(100), default='Подробнее')
    is_active   = db.Column(db.Boolean, default=True)
    order       = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<Banner {self.title}>'


class Message(db.Model):
    """Сообщение из формы обратной связи."""
    __tablename__ = 'messages'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    email      = db.Column(db.String(200), nullable=False)
    phone      = db.Column(db.String(20))
    subject    = db.Column(db.String(300))
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read    = db.Column(db.Boolean, default=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f'<Message от {self.name}>'


class Promotion(db.Model):
    """Акция / специальное предложение."""
    __tablename__ = 'promotions'

    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text)
    discount_text = db.Column(db.String(50))   # Например «20%» или «3=2»
    image         = db.Column(db.String(255))
    promo_code    = db.Column(db.String(50))
    start_date    = db.Column(db.DateTime)
    end_date      = db.Column(db.DateTime)
    is_active     = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Promotion {self.title}>'


class Order(db.Model):
    """Заказ покупателя."""
    __tablename__ = 'orders'

    # Статусы заказа
    STATUS_NEW        = 'new'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED    = 'shipped'
    STATUS_DELIVERED  = 'delivered'
    STATUS_CANCELLED  = 'cancelled'

    STATUS_LABELS = {
        'new':        'Новый',
        'processing': 'В обработке',
        'shipped':    'Отправлен',
        'delivered':  'Доставлен',
        'cancelled':  'Отменён',
    }

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # Данные получателя
    full_name      = db.Column(db.String(200), nullable=False)
    phone          = db.Column(db.String(30),  nullable=False)
    email          = db.Column(db.String(200), nullable=False)
    # Доставка
    delivery_type  = db.Column(db.String(20), default='courier')   # courier / pickup
    address        = db.Column(db.String(400))                      # для курьера
    # Оплата
    payment_type   = db.Column(db.String(20), default='cash')      # cash / card / online
    comment        = db.Column(db.Text)
    # Финансы
    total          = db.Column(db.Float, nullable=False, default=0)
    promo_code     = db.Column(db.String(50))
    # Статус и дата
    status         = db.Column(db.String(20), default='new', nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    items    = db.relationship('OrderItem', backref='order', lazy=True,
                               cascade='all, delete-orphan')
    customer = db.relationship('User', backref='orders', lazy=True)

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def items_count(self):
        return sum(i.qty for i in self.items)

    def __repr__(self):
        return f'<Order #{self.id} {self.status}>'


class OrderItem(db.Model):
    """Позиция в заказе (снимок товара на момент покупки)."""
    __tablename__ = 'order_items'

    id           = db.Column(db.Integer, primary_key=True)
    order_id     = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id   = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)   # копия на момент заказа
    price        = db.Column(db.Float, nullable=False)
    qty          = db.Column(db.Integer, nullable=False, default=1)

    product = db.relationship('Product', lazy=True)

    @property
    def subtotal(self):
        return self.price * self.qty

    def __repr__(self):
        return f'<OrderItem {self.product_name} ×{self.qty}>'


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    """Загрузчик пользователя для Flask-Login."""
    return User.query.get(int(user_id))


def admin_required(f):
    """Декоратор: доступ только для администраторов."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    """Декоратор: доступ для менеджеров и администраторов."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_manager():
            abort(403)
        return f(*args, **kwargs)
    return decorated


def slugify(text: str) -> str:
    """Преобразует строку в URL-совместимый slug (с транслитерацией)."""
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    result = ''
    for ch in text.lower():
        result += translit.get(ch, ch if ch.isalnum() else '-')
    result = re.sub(r'-+', '-', result).strip('-')
    return result[:200]


# ============================================================
# КОНТЕКСТНЫЙ ПРОЦЕССОР (глобальные переменные шаблонов)
# ============================================================

@app.context_processor
def inject_globals():
    """Передаёт общие переменные во все шаблоны."""
    cats = Category.query.order_by(Category.order).all()
    cart = session.get('cart', {})
    cart_count = sum(cart.values()) if cart else 0
    return {
        'categories': cats,
        'cart_count': cart_count,
        'current_year': datetime.utcnow().year,
        'site_name': 'ДомашнийУют',
    }


# ============================================================
# МАРШРУТЫ: АУТЕНТИФИКАЦИЯ
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        # Поиск по имени пользователя или email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Добро пожаловать, {user.full_name or user.username}!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверный логин или пароль. Попробуйте ещё раз.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница самостоятельной регистрации пользователя."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        email     = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        phone     = request.form.get('phone', '').strip()
        password  = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        errors = []
        if len(username) < 3:
            errors.append('Имя пользователя должно содержать не менее 3 символов.')
        if User.query.filter_by(username=username).first():
            errors.append('Это имя пользователя уже занято.')
        if not email or '@' not in email:
            errors.append('Введите корректный адрес электронной почты.')
        if User.query.filter_by(email=email).first():
            errors.append('Этот email уже зарегистрирован.')
        if len(password) < 6:
            errors.append('Пароль должен содержать не менее 6 символов.')
        if password != password2:
            errors.append('Пароли не совпадают.')

        if errors:
            for err in errors:
                flash(err, 'danger')
        else:
            user = User(username=username, email=email,
                        full_name=full_name, phone=phone, role='user')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Регистрация прошла успешно! Добро пожаловать в ДомашнийУют!', 'success')
            return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    """Завершение сеанса пользователя."""
    logout_user()
    flash('Вы вышли из системы. До свидания!', 'info')
    return redirect(url_for('index'))


# ============================================================
# МАРШРУТЫ: ОСНОВНЫЕ СТРАНИЦЫ (стр. 1–10)
# ============================================================

@app.route('/')
def index():
    """Страница 1 — Главная."""
    banners         = Banner.query.filter_by(is_active=True).order_by(Banner.order).all()
    featured        = Product.query.filter_by(is_featured=True).limit(8).all()
    new_products    = Product.query.filter_by(is_new=True).limit(6).all()
    latest_news     = (NewsArticle.query.filter_by(is_published=True)
                       .order_by(NewsArticle.created_at.desc()).limit(3).all())
    active_promos   = Promotion.query.filter_by(is_active=True).limit(3).all()

    return render_template('index.html',
                           banners=banners,
                           featured=featured,
                           new_products=new_products,
                           latest_news=latest_news,
                           active_promos=active_promos)


@app.route('/catalog')
@app.route('/catalog/<string:category_slug>')
def catalog(category_slug=None):
    """Страница 2 — Каталог товаров с фильтрами и пагинацией."""
    current_category = None
    query = Product.query

    if category_slug:
        current_category = Category.query.filter_by(slug=category_slug).first_or_404()
        query = query.filter_by(category_id=current_category.id)

    # Параметры фильтрации
    price_min    = request.args.get('price_min', type=float)
    price_max    = request.args.get('price_max', type=float)
    filter_new   = request.args.get('new')
    filter_sale  = request.args.get('sale')
    sort         = request.args.get('sort', 'default')
    search_q     = request.args.get('q', '').strip()

    if price_min is not None:
        query = query.filter(Product.price >= price_min)
    if price_max is not None:
        query = query.filter(Product.price <= price_max)
    if filter_new:
        query = query.filter_by(is_new=True)
    if filter_sale:
        query = query.filter_by(is_sale=True)
    if search_q:
        query = query.filter(Product.name.ilike(f'%{search_q}%'))

    # Сортировка
    sort_map = {
        'price_asc':  Product.price.asc(),
        'price_desc': Product.price.desc(),
        'newest':     Product.created_at.desc(),
    }
    query = query.order_by(sort_map.get(sort, Product.is_featured.desc()))

    page     = request.args.get('page', 1, type=int)
    products = query.paginate(page=page, per_page=12, error_out=False)

    return render_template('catalog.html',
                           products=products,
                           current_category=current_category,
                           search_q=search_q,
                           sort=sort)


@app.route('/product/<string:slug>')
def product_detail(slug):
    """Страница 3 — Карточка товара."""
    product = Product.query.filter_by(slug=slug).first_or_404()
    related = (Product.query
               .filter_by(category_id=product.category_id)
               .filter(Product.id != product.id)
               .limit(4).all())
    return render_template('product.html', product=product, related=related)


@app.route('/news')
def news():
    """Страница 4 — Список новостей с фильтром по категории."""
    cat_filter = request.args.get('category', '')
    page       = request.args.get('page', 1, type=int)

    query = NewsArticle.query.filter_by(is_published=True)
    if cat_filter:
        query = query.filter_by(category=cat_filter)

    articles       = query.order_by(NewsArticle.created_at.desc()).paginate(page=page, per_page=9, error_out=False)
    news_categories = [c[0] for c in db.session.query(NewsArticle.category).distinct().all()]

    return render_template('news.html',
                           articles=articles,
                           news_categories=news_categories,
                           current_category=cat_filter)


@app.route('/news/<string:slug>')
def news_detail(slug):
    """Страница 5 — Отдельная новость/статья."""
    article = NewsArticle.query.filter_by(slug=slug, is_published=True).first_or_404()
    article.views += 1   # Увеличиваем счётчик просмотров
    db.session.commit()

    related = (NewsArticle.query
               .filter_by(category=article.category, is_published=True)
               .filter(NewsArticle.id != article.id)
               .limit(3).all())
    return render_template('news_detail.html', article=article, related=related)


@app.route('/about')
def about():
    """Страница 6 — О компании."""
    return render_template('about.html')


@app.route('/contacts', methods=['GET', 'POST'])
def contacts():
    """Страница 7 — Контакты и форма обратной связи."""
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        phone   = request.form.get('phone', '').strip()
        subject = request.form.get('subject', '').strip()
        content = request.form.get('content', '').strip()

        if not name or not email or not content:
            flash('Пожалуйста, заполните все обязательные поля.', 'danger')
        else:
            msg = Message(
                name=name, email=email, phone=phone,
                subject=subject, content=content,
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(msg)
            db.session.commit()
            flash('Ваше сообщение отправлено! Мы ответим в течение 24 часов.', 'success')
            return redirect(url_for('contacts'))

    return render_template('contacts.html')


@app.route('/promotions')
def promotions():
    """Страница 8 — Акции и скидки."""
    active_promos = Promotion.query.filter_by(is_active=True).all()
    sale_products = Product.query.filter_by(is_sale=True).limit(12).all()
    return render_template('promotions.html',
                           promotions=active_promos,
                           sale_products=sale_products)


@app.route('/profile')
@login_required
def profile():
    """Страница 9 — Личный кабинет пользователя."""
    user_msgs = (Message.query
                 .filter_by(user_id=current_user.id)
                 .order_by(Message.created_at.desc())
                 .limit(10).all())
    return render_template('profile.html', user_messages=user_msgs)


@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    """Обновление данных профиля текущего пользователя."""
    current_user.full_name = request.form.get('full_name', '').strip()
    current_user.phone     = request.form.get('phone', '').strip()

    new_pw = request.form.get('new_password', '')
    if new_pw:
        if len(new_pw) < 6:
            flash('Новый пароль должен содержать не менее 6 символов.', 'danger')
            return redirect(url_for('profile'))
        if not current_user.check_password(request.form.get('current_password', '')):
            flash('Неверный текущий пароль.', 'danger')
            return redirect(url_for('profile'))
        current_user.set_password(new_pw)

    db.session.commit()
    flash('Профиль успешно обновлён.', 'success')
    return redirect(url_for('profile'))


# ============================================================
# МАРШРУТЫ: КОРЗИНА (сессионная)
# ============================================================

@app.route('/cart')
def cart_view():
    """Страница корзины покупателя."""
    cart  = session.get('cart', {})
    items = []
    total = 0.0
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            sub = product.price * qty
            items.append({'product': product, 'qty': qty, 'subtotal': sub})
            total += sub
    return render_template('cart.html', items=items, total=total)


@app.route('/cart/add/<int:product_id>', methods=['POST'])
def cart_add(product_id):
    """Добавление товара в корзину."""
    product = Product.query.get_or_404(product_id)
    cart = session.get('cart', {})
    key  = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    session['cart'] = cart

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'count': sum(cart.values()),
                        'name': product.name})

    flash(f'«{product.name}» добавлен в корзину.', 'success')
    return redirect(request.referrer or url_for('catalog'))


@app.route('/cart/remove/<int:product_id>', methods=['POST'])
def cart_remove(product_id):
    """Удаление позиции из корзины."""
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    flash('Товар удалён из корзины.', 'info')
    return redirect(url_for('cart_view'))


@app.route('/cart/update/<int:product_id>', methods=['POST'])
def cart_update(product_id):
    """Изменение количества товара в корзине."""
    qty  = request.form.get('qty', 1, type=int)
    cart = session.get('cart', {})
    if qty <= 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = qty
    session['cart'] = cart
    return redirect(url_for('cart_view'))


@app.route('/cart/clear', methods=['POST'])
def cart_clear():
    """Очистка корзины."""
    session.pop('cart', None)
    flash('Корзина очищена.', 'info')
    return redirect(url_for('cart_view'))


# ============================================================
# МАРШРУТЫ: ОФОРМЛЕНИЕ ЗАКАЗА
# ============================================================

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Страница оформления заказа."""
    cart = session.get('cart', {})
    if not cart:
        flash('Корзина пуста. Добавьте товары перед оформлением заказа.', 'warning')
        return redirect(url_for('cart_view'))

    # Собираем позиции из корзины
    items = []
    total = 0.0
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            sub = product.price * qty
            items.append({'product': product, 'qty': qty, 'subtotal': sub})
            total += sub

    if request.method == 'POST':
        full_name     = request.form.get('full_name', '').strip()
        phone         = request.form.get('phone', '').strip()
        email         = request.form.get('email', '').strip()
        delivery_type = request.form.get('delivery_type', 'courier')
        address       = request.form.get('address', '').strip()
        payment_type  = request.form.get('payment_type', 'cash')
        comment       = request.form.get('comment', '').strip()
        promo_code    = request.form.get('promo_code', '').strip().upper()

        # Валидация
        errors = []
        if not full_name:
            errors.append('Укажите имя получателя.')
        if not phone:
            errors.append('Укажите номер телефона.')
        if not email or '@' not in email:
            errors.append('Укажите корректный email.')
        if delivery_type == 'courier' and not address:
            errors.append('Укажите адрес доставки.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('checkout.html', items=items, total=total,
                                   form=request.form)

        # Создаём заказ
        order = Order(
            user_id=current_user.id,
            full_name=full_name,
            phone=phone,
            email=email,
            delivery_type=delivery_type,
            address=address if delivery_type == 'courier' else 'Самовывоз',
            payment_type=payment_type,
            comment=comment,
            total=total,
            promo_code=promo_code or None,
            status=Order.STATUS_NEW,
        )
        db.session.add(order)
        db.session.flush()   # получаем order.id до commit

        # Создаём позиции заказа (снимок цен)
        for item in items:
            oi = OrderItem(
                order_id=order.id,
                product_id=item['product'].id,
                product_name=item['product'].name,
                price=item['product'].price,
                qty=item['qty'],
            )
            db.session.add(oi)

        db.session.commit()

        # Очищаем корзину
        session.pop('cart', None)

        flash(f'Заказ №{order.id} успешно оформлен! Мы свяжемся с вами в ближайшее время.', 'success')
        return redirect(url_for('order_success', order_id=order.id))

    # Предзаполнение из профиля
    form_defaults = {
        'full_name': current_user.full_name or '',
        'phone':     current_user.phone or '',
        'email':     current_user.email or '',
    }
    return render_template('checkout.html', items=items, total=total, form=form_defaults)


@app.route('/order/<int:order_id>')
@login_required
def order_success(order_id):
    """Страница подтверждения заказа."""
    order = Order.query.get_or_404(order_id)
    # Только владелец заказа или менеджер может видеть
    if order.user_id != current_user.id and not current_user.is_manager():
        abort(403)
    return render_template('order_success.html', order=order)


@app.route('/profile/orders')
@login_required
def profile_orders():
    """История заказов текущего пользователя."""
    orders = (Order.query
              .filter_by(user_id=current_user.id)
              .order_by(Order.created_at.desc())
              .all())
    return render_template('profile_orders.html', orders=orders)


# ============================================================
# МАРШРУТЫ: ЗАКАЗЫ В ПАНЕЛИ АДМИНИСТРАТОРА
# ============================================================

@app.route('/admin/orders')
@login_required
@manager_required
def admin_orders():
    """Список всех заказов."""
    status_filter = request.args.get('status', '')
    page          = request.args.get('page', 1, type=int)

    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    orders = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_orders.html',
                           orders=orders,
                           status_filter=status_filter,
                           statuses=Order.STATUS_LABELS)


@app.route('/admin/orders/<int:order_id>')
@login_required
@manager_required
def admin_order_detail(order_id):
    """Детали заказа в панели администратора."""
    order = Order.query.get_or_404(order_id)
    return render_template('admin_order_detail.html',
                           order=order,
                           statuses=Order.STATUS_LABELS)


@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@login_required
@manager_required
def admin_order_status(order_id):
    """Изменение статуса заказа."""
    order      = Order.query.get_or_404(order_id)
    new_status = request.form.get('status', '')
    if new_status in Order.STATUS_LABELS:
        order.status = new_status
        db.session.commit()
        flash(f'Статус заказа №{order.id} изменён на «{order.status_label}».', 'success')
    else:
        flash('Недопустимый статус.', 'danger')
    return redirect(url_for('admin_order_detail', order_id=order_id))


# ============================================================
# МАРШРУТЫ: ПОИСК
# ============================================================

@app.route('/search')
def search():
    """Страница результатов поиска."""
    q        = request.args.get('q', '').strip()
    products = []
    articles = []
    if q:
        products = Product.query.filter(
            Product.name.ilike(f'%{q}%') | Product.description.ilike(f'%{q}%')
        ).limit(20).all()
        articles = NewsArticle.query.filter(
            (NewsArticle.title.ilike(f'%{q}%') | NewsArticle.preview.ilike(f'%{q}%')),
            NewsArticle.is_published == True
        ).limit(10).all()
    return render_template('search.html', query=q, products=products, articles=articles)


@app.route('/api/search')
def api_search():
    """AJAX-эндпоинт для живого поиска в шапке сайта."""
    q       = request.args.get('q', '').strip()
    results = []
    if len(q) >= 2:
        for p in Product.query.filter(Product.name.ilike(f'%{q}%')).limit(6).all():
            results.append({
                'type':  'product',
                'name':  p.name,
                'price': f'{p.price:,.0f} ₽',
                'url':   url_for('product_detail', slug=p.slug),
                'image': p.image,
            })
        for a in NewsArticle.query.filter(
            NewsArticle.title.ilike(f'%{q}%'), NewsArticle.is_published == True
        ).limit(3).all():
            results.append({
                'type':  'article',
                'name':  a.title,
                'price': '',
                'url':   url_for('news_detail', slug=a.slug),
                'image': a.image,
            })
    return jsonify(results)


# ============================================================
# МАРШРУТЫ: СТРАНИЦА 10 — ПАНЕЛЬ АДМИНИСТРАТОРА
# ============================================================

@app.route('/admin')
@login_required
@manager_required
def admin():
    """Страница 10 — Панель управления (менеджер/администратор)."""
    stats = {
        'products':        Product.query.count(),
        'users':           User.query.count(),
        'news':            NewsArticle.query.count(),
        'messages':        Message.query.count(),
        'unread_messages': Message.query.filter_by(is_read=False).count(),
        'promotions':      Promotion.query.count(),
        'orders':          Order.query.count(),
        'orders_new':      Order.query.filter_by(status=Order.STATUS_NEW).count(),
    }
    recent_messages = Message.query.order_by(Message.created_at.desc()).limit(10).all()
    recent_users    = User.query.order_by(User.created_at.desc()).limit(10).all()
    return render_template('admin.html',
                           stats=stats,
                           recent_messages=recent_messages,
                           recent_users=recent_users)


@app.route('/admin/messages/<int:msg_id>/read', methods=['POST'])
@login_required
@manager_required
def admin_message_read(msg_id):
    """Отмечает сообщение прочитанным (AJAX)."""
    msg = Message.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Список пользователей (только администратор)."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_user_create():
    """Создание нового пользователя администратором (сценарий №1)."""
    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        email     = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        phone     = request.form.get('phone', '').strip()
        password  = request.form.get('password', '')
        role      = request.form.get('role', 'user')

        errors = []
        if len(username) < 3:
            errors.append('Имя пользователя — минимум 3 символа.')
        if User.query.filter_by(username=username).first():
            errors.append('Пользователь с таким именем уже существует.')
        if not email or '@' not in email:
            errors.append('Некорректный email.')
        if User.query.filter_by(email=email).first():
            errors.append('Пользователь с таким email уже существует.')
        if len(password) < 6:
            errors.append('Пароль — минимум 6 символов.')
        if role not in ('admin', 'manager', 'user'):
            errors.append('Недопустимая роль.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            new_user = User(username=username, email=email,
                            full_name=full_name, phone=phone, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash(f'Пользователь «{username}» успешно создан.', 'success')
            return redirect(url_for('admin_users'))

    return render_template('admin_user_create.html')


@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_user_toggle(user_id):
    """Блокировка / разблокировка пользователя."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Невозможно заблокировать собственную учётную запись.', 'danger')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        status = 'разблокирован' if user.is_active else 'заблокирован'
        flash(f'Пользователь «{user.username}» {status}.', 'success')
    return redirect(url_for('admin_users'))


# ============================================================
# МАРШРУТЫ: CRUD ТОВАРОВ (панель администратора)
# ============================================================

@app.route('/admin/products')
@login_required
@manager_required
def admin_products():
    """Список всех товаров с возможностью поиска."""
    q    = request.args.get('q', '').strip()
    cat  = request.args.get('cat', '', type=str)
    page = request.args.get('page', 1, type=int)

    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))
    if cat:
        query = query.filter(Product.category_id == int(cat)) if cat.isdigit() else query

    products = query.order_by(Product.id.desc()).paginate(page=page, per_page=20, error_out=False)
    categories = Category.query.order_by(Category.order).all()
    return render_template('admin_products.html',
                           products=products, search_q=q,
                           selected_cat=cat, categories=categories)


@app.route('/admin/products/create', methods=['GET', 'POST'])
@login_required
@manager_required
def admin_product_create():
    """Создание нового товара."""
    categories = Category.query.order_by(Category.order).all()
    if request.method == 'POST':
        name      = request.form.get('name', '').strip()
        cat_id    = request.form.get('category_id', type=int)
        price     = request.form.get('price', type=float)
        old_price = request.form.get('old_price', '').strip()
        desc      = request.form.get('description', '').strip()
        full_desc = request.form.get('full_description', '').strip()
        image     = request.form.get('image', '').strip()
        stock     = request.form.get('stock', 100, type=int)
        is_featured = bool(request.form.get('is_featured'))
        is_new      = bool(request.form.get('is_new'))
        is_sale     = bool(request.form.get('is_sale'))

        errors = []
        if len(name) < 2:
            errors.append('Название товара — минимум 2 символа.')
        if not cat_id:
            errors.append('Выберите категорию.')
        if price is None or price <= 0:
            errors.append('Укажите корректную цену.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            slug = slugify(name)
            # Если slug занят — добавляем суффикс
            base_slug, n = slug, 1
            while Product.query.filter_by(slug=slug).first():
                slug = f'{base_slug}-{n}'; n += 1

            p = Product(
                name=name, slug=slug, category_id=cat_id,
                price=price,
                old_price=float(old_price) if old_price else None,
                description=desc, full_description=full_desc,
                image=image or f'https://picsum.photos/seed/{slug[:12]}/400/300',
                stock=stock,
                is_featured=is_featured, is_new=is_new, is_sale=is_sale,
            )
            db.session.add(p)
            db.session.commit()
            flash(f'Товар «{name}» успешно добавлен.', 'success')
            return redirect(url_for('admin_products'))

    return render_template('admin_product_form.html',
                           categories=categories, product=None, action='create')


@app.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def admin_product_edit(product_id):
    """Редактирование существующего товара."""
    product    = Product.query.get_or_404(product_id)
    categories = Category.query.order_by(Category.order).all()

    if request.method == 'POST':
        product.name      = request.form.get('name', '').strip()
        cat_id            = request.form.get('category_id', type=int)
        product.price     = request.form.get('price', type=float)
        old_price         = request.form.get('old_price', '').strip()
        product.old_price = float(old_price) if old_price else None
        product.description      = request.form.get('description', '').strip()
        product.full_description = request.form.get('full_description', '').strip()
        product.image     = request.form.get('image', '').strip()
        product.stock     = request.form.get('stock', 100, type=int)
        product.is_featured = bool(request.form.get('is_featured'))
        product.is_new      = bool(request.form.get('is_new'))
        product.is_sale     = bool(request.form.get('is_sale'))

        errors = []
        if len(product.name) < 2:
            errors.append('Название товара — минимум 2 символа.')
        if not cat_id:
            errors.append('Выберите категорию.')
        if not product.price or product.price <= 0:
            errors.append('Укажите корректную цену.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            product.category_id = cat_id
            db.session.commit()
            flash(f'Товар «{product.name}» обновлён.', 'success')
            return redirect(url_for('admin_products'))

    return render_template('admin_product_form.html',
                           categories=categories, product=product, action='edit')


@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_product_delete(product_id):
    """Удаление товара (только администратор)."""
    product = Product.query.get_or_404(product_id)
    name    = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'Товар «{name}» удалён.', 'info')
    return redirect(url_for('admin_products'))


# ============================================================
# МАРШРУТЫ: CRUD НОВОСТЕЙ (панель администратора)
# ============================================================

@app.route('/admin/news')
@login_required
@manager_required
def admin_news_list():
    """Список всех новостей/статей."""
    q    = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = NewsArticle.query
    if q:
        query = query.filter(NewsArticle.title.ilike(f'%{q}%'))

    articles = query.order_by(NewsArticle.id.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_news_list.html', articles=articles, search_q=q)


@app.route('/admin/news/create', methods=['GET', 'POST'])
@login_required
@manager_required
def admin_news_create():
    """Создание новой статьи."""
    if request.method == 'POST':
        title        = request.form.get('title', '').strip()
        category     = request.form.get('category', '').strip()
        preview      = request.form.get('preview', '').strip()
        content      = request.form.get('content', '').strip()
        image        = request.form.get('image', '').strip()
        is_published = bool(request.form.get('is_published'))

        errors = []
        if len(title) < 3:
            errors.append('Заголовок — минимум 3 символа.')
        if not content:
            errors.append('Содержание статьи не может быть пустым.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            slug = slugify(title)
            base_slug, n = slug, 1
            while NewsArticle.query.filter_by(slug=slug).first():
                slug = f'{base_slug}-{n}'; n += 1

            art = NewsArticle(
                title=title, slug=slug, category=category or 'Новости',
                preview=preview, content=content,
                image=image or f'https://picsum.photos/seed/{slug[:10]}/800/400',
                author_id=current_user.id,
                is_published=is_published,
            )
            db.session.add(art)
            db.session.commit()
            flash(f'Статья «{title}» опубликована.', 'success')
            return redirect(url_for('admin_news_list'))

    return render_template('admin_news_form.html', article=None, action='create')


@app.route('/admin/news/<int:article_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def admin_news_edit(article_id):
    """Редактирование статьи."""
    article = NewsArticle.query.get_or_404(article_id)

    if request.method == 'POST':
        article.title        = request.form.get('title', '').strip()
        article.category     = request.form.get('category', '').strip() or 'Новости'
        article.preview      = request.form.get('preview', '').strip()
        article.content      = request.form.get('content', '').strip()
        article.image        = request.form.get('image', '').strip()
        article.is_published = bool(request.form.get('is_published'))

        errors = []
        if len(article.title) < 3:
            errors.append('Заголовок — минимум 3 символа.')
        if not article.content:
            errors.append('Содержание статьи не может быть пустым.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            db.session.commit()
            flash(f'Статья «{article.title}» обновлена.', 'success')
            return redirect(url_for('admin_news_list'))

    return render_template('admin_news_form.html', article=article, action='edit')


@app.route('/admin/news/<int:article_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_news_delete(article_id):
    """Удаление статьи (только администратор)."""
    article = NewsArticle.query.get_or_404(article_id)
    title   = article.title
    db.session.delete(article)
    db.session.commit()
    flash(f'Статья «{title}» удалена.', 'info')
    return redirect(url_for('admin_news_list'))


# ============================================================
# МАРШРУТЫ: CRUD АКЦИЙ (панель администратора)
# ============================================================

@app.route('/admin/promotions')
@login_required
@manager_required
def admin_promotions_list():
    """Список всех акций."""
    promos = Promotion.query.order_by(Promotion.id.desc()).all()
    return render_template('admin_promotions.html', promos=promos)


@app.route('/admin/promotions/create', methods=['GET', 'POST'])
@login_required
@manager_required
def admin_promo_create():
    """Создание новой акции."""
    if request.method == 'POST':
        title         = request.form.get('title', '').strip()
        description   = request.form.get('description', '').strip()
        discount_text = request.form.get('discount_text', '').strip()
        promo_code    = request.form.get('promo_code', '').strip()
        image         = request.form.get('image', '').strip()
        is_active     = bool(request.form.get('is_active'))

        if not title:
            flash('Название акции не может быть пустым.', 'danger')
        else:
            promo = Promotion(
                title=title, description=description,
                discount_text=discount_text,
                promo_code=promo_code or None,
                image=image or f'https://picsum.photos/seed/promo{title[:6]}/600/400',
                is_active=is_active,
            )
            db.session.add(promo)
            db.session.commit()
            flash(f'Акция «{title}» добавлена.', 'success')
            return redirect(url_for('admin_promotions_list'))

    return render_template('admin_promo_form.html', promo=None, action='create')


@app.route('/admin/promotions/<int:promo_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def admin_promo_edit(promo_id):
    """Редактирование акции."""
    promo = Promotion.query.get_or_404(promo_id)

    if request.method == 'POST':
        promo.title         = request.form.get('title', '').strip()
        promo.description   = request.form.get('description', '').strip()
        promo.discount_text = request.form.get('discount_text', '').strip()
        promo.promo_code    = request.form.get('promo_code', '').strip() or None
        promo.image         = request.form.get('image', '').strip()
        promo.is_active     = bool(request.form.get('is_active'))

        if not promo.title:
            flash('Название акции не может быть пустым.', 'danger')
        else:
            db.session.commit()
            flash(f'Акция «{promo.title}» обновлена.', 'success')
            return redirect(url_for('admin_promotions_list'))

    return render_template('admin_promo_form.html', promo=promo, action='edit')


@app.route('/admin/promotions/<int:promo_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_promo_delete(promo_id):
    """Удаление акции (только администратор)."""
    promo = Promotion.query.get_or_404(promo_id)
    title = promo.title
    db.session.delete(promo)
    db.session.commit()
    flash(f'Акция «{title}» удалена.', 'info')
    return redirect(url_for('admin_promotions_list'))


# ============================================================
# МАРШРУТЫ: КАРТА САЙТА И ОБРАБОТЧИКИ ОШИБОК
# ============================================================

@app.route('/sitemap')
def sitemap():
    """Карта сайта (не учитывается при подсчёте страниц)."""
    cats      = Category.query.order_by(Category.order).all()
    news_list = (NewsArticle.query.filter_by(is_published=True)
                 .order_by(NewsArticle.created_at.desc()).all())
    return render_template('sitemap.html', categories=cats, news_list=news_list)


@app.errorhandler(404)
def page_not_found(e):
    """Обработчик ошибки 404 — страница не найдена."""
    return render_template('404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    """Обработчик ошибки 403 — доступ запрещён."""
    return render_template('403.html'), 403


@app.errorhandler(500)
def server_error(e):
    """Обработчик ошибки 500 — внутренняя ошибка сервера."""
    return render_template('500.html'), 500


# ============================================================
# НАПОЛНЕНИЕ БАЗЫ ДАННЫХ ТЕСТОВЫМИ ДАННЫМИ
# ============================================================

def seed_database():
    """Создаёт начальный набор данных: пользователи, категории, товары, новости, баннеры, акции."""

    # --- Пользователи ---
    users_seed = [
        ('admin',   'admin@domashniuyt.ru',    'Администратор Системы',    '',                'admin',   'admin123'),
        ('manager', 'manager@domashniuyt.ru',   'Елена Иванова (Менеджер)', '+7(495)123-45-67','manager', 'manager123'),
        ('user1',   'user1@example.com',        'Иван Петров',              '+7(916)555-00-11','user',    'user1234'),
        ('user2',   'user2@example.com',        'Мария Смирнова',           '+7(926)777-22-33','user',    'user5678'),
    ]
    for uname, email, full, phone, role, pw in users_seed:
        if not User.query.filter_by(username=uname).first():
            u = User(username=uname, email=email, full_name=full, phone=phone, role=role)
            u.set_password(pw)
            db.session.add(u)
    db.session.commit()

    # --- Категории ---
    cats_seed = [
        ('Мебель',     'mebel',       'Диваны, кресла, столы, кровати и корпусная мебель',           'bi-lamp-fill',    1),
        ('Текстиль',   'tekstil',     'Постельное бельё, шторы, пледы, подушки, ковры',              'bi-bag-heart-fill',2),
        ('Кухня',      'kuhnya',      'Посуда, кухонные принадлежности и аксессуары',                'bi-cup-hot-fill',  3),
        ('Декор',      'dekor',       'Вазы, картины, свечи и украшения для интерьера',              'bi-stars',         4),
        ('Освещение',  'osveshchenie','Люстры, торшеры, настольные лампы и светильники',             'bi-lightbulb-fill',5),
        ('Хранение',   'hranenie',    'Органайзеры, корзины, полки и системы хранения',              'bi-archive-fill',  6),
    ]
    cat_map = {}
    for name, slug, desc, icon, order in cats_seed:
        c = Category.query.filter_by(slug=slug).first()
        if not c:
            c = Category(name=name, slug=slug, description=desc, icon=icon, order=order)
            db.session.add(c)
            db.session.flush()
        cat_map[slug] = c
    db.session.commit()

    # --- Товары (6+ на категорию) ---
    products_seed = [
        # Мебель
        ('Диван угловой «Комфорт Плюс»',        'mebel',       45990, 55990, True,  True,  False, 'Просторный угловой диван-трансформер с мягкими подушками и механизмом раскладки. Обивка — велюр.'),
        ('Кресло-реклайнер «Релакс»',           'mebel',       18990, None,  False, True,  False, 'Электрическое кресло с откидывающейся спинкой и подставкой для ног. Массажная функция.'),
        ('Кровать «Скандинавия» 160×200',       'mebel',       29990, 34990, False, False, True,  'Деревянная кровать в скандинавском стиле с реечным основанием и мягким изголовьем.'),
        ('Стол обеденный раздвижной «Дуб»',     'mebel',       14990, None,  True,  False, False, 'Раздвижной стол из массива дуба, рассчитан на 6–10 персон. Покрытие маслом.'),
        ('Стул «Модерн» (мягкий)',              'mebel',        3990,  4990, False, False, True,  'Мягкий стул на буковых ножках с тканевой обивкой. Высота сиденья 47 см.'),
        ('Тумба прикроватная «Лофт»',          'mebel',        5990,  None, False, True,  False, 'Прикроватная тумба из дерева и металла в стиле лофт с двумя ящиками.'),
        ('Шкаф-купе «Классика» 200×240',       'mebel',       39990, 49990, False, False, True,  'Двухдверный шкаф-купе с зеркальными фасадами, регулируемыми полками и штангой.'),
        # Текстиль
        ('Постельный комплект «Прованс»',       'tekstil',      3490,  None, True,  True,  False, 'Сатиновое бельё с цветочным принтом, 100 % хлопок, евро размер (200×220 см).'),
        ('Шторы блэкаут «Уют» 260 см',         'tekstil',      4990,  6990, False, False, True,  'Затемняющие шторы из плотного жаккарда. Высота 260 см. 2 полотна в комплекте.'),
        ('Плед вязаный «Тепло» 130×180',       'tekstil',      2490,  None, True,  True,  False, 'Мягкий крупновязаный плед из акрила. Размер 130×180 см. 5 расцветок.'),
        ('Подушки декоративные (набор 2 шт.)', 'tekstil',      1990,  2490, False, False, True,  'Комплект декоративных подушек 45×45 см с набивным принтом.'),
        ('Ковёр «Марокко» 150×230',            'tekstil',      8990, 11990, False, False, True,  'Безворсовый ковёр с геометрическим орнаментом. Материал: хлопок + полипропилен.'),
        ('Банный коврик антискользящий',        'tekstil',       990,  None, False, True,  False, 'Микрофибровый коврик 50×80 см с антискользящей основой.'),
        # Кухня
        ('Набор посуды «Гурмэ» 12 пр.',        'kuhnya',       7990,  9990, True,  True,  False, '12 предметов: кастрюли, сотейник, сковорода. Нержавеющая сталь, антипригарное покрытие.'),
        ('Сковорода чугунная 28 см',           'kuhnya',       3990,  None, False, True,  False, 'Классическая литая чугунная сковорода с долговечным покрытием и деревянной ручкой.'),
        ('Кастрюля «Профи» 6 л',              'kuhnya',       2990,  3490, False, False, True,  'Кастрюля из нержавеющей стали с двойным дном и крышкой. Подходит для индукции.'),
        ('Нож шефский «Дамаск» 20 см',        'kuhnya',       5490,  None, True,  False, False, 'Профессиональный нож из 67-слойной дамасской стали с рукоятью из пакки.'),
        ('Блендер погружной «Смузи»',          'kuhnya',       4990,  6990, False, False, True,  'Мощный погружной блендер 1000 Вт с насадками, мерным стаканом и чашей для измельчения.'),
        ('Доска разделочная бамбуковая 35×25', 'kuhnya',        890,  None, False, True,  False, 'Экологичная разделочная доска из бамбука. Антибактериальный материал.'),
        # Декор
        ('Ваза напольная «Тоскана» h70 см',   'dekor',        6990,  None, True,  True,  False, 'Керамическая ваза в средиземноморском стиле, высота 70 см. Ручная роспись.'),
        ('Фоторамки деревянные (набор 3 шт.)', 'dekor',        1490,  1990, False, False, True,  'Рамки из натурального дерева для фото 10×15, 15×21, 20×30 см.'),
        ('Свечи ароматические «Лаванда»',      'dekor',         990,  None, False, True,  False, 'Набор из 3 натуральных соевых свечей с ароматом лаванды. Время горения — 30 ч.'),
        ('Картина на холсте «Закат» 60×80',   'dekor',        3990,  4990, False, False, True,  'Репродукция на натуральном льняном холсте в деревянном подрамнике.'),
        ('Часы настенные «Минимализм» Ø40',   'dekor',        2490,  None, True,  False, False, 'Бесшумные часы (плавный ход) в скандинавском стиле. Диаметр 40 см.'),
        ('Зеркало в кованой раме 60×90',       'dekor',        4990,  5990, False, False, True,  'Декоративное зеркало с кованой рамой ручной работы. Можно вешать вертикально и горизонтально.'),
        # Освещение
        ('Люстра «Хрусталь» 6 плафонов',      'osveshchenie', 12990, 16990, True, False, True,  'Классическая хрустальная люстра на 6 плафонов E14. Диаметр 70 см.'),
        ('Торшер «Скандинавия»',              'osveshchenie',  5990,  None, False, True,  False, 'Торшер в скандинавском стиле с регулируемой яркостью. Тканевый абажур.'),
        ('Настольная лампа LED «Офис»',       'osveshchenie',  3490,  4490, False, False, True,  'LED-лампа с гибким рычагом, регулятором яркостью и USB-зарядкой. Мощность 12 Вт.'),
        ('Ночник-проектор «Звёздное небо»',   'osveshchenie',  1990,  None, False, True,  False, 'Световой проектор с 7 цветами подсветки и таймером отключения.'),
        ('Светодиодная лента RGB 5 м',        'osveshchenie',  1490,  1990, False, False, True,  'Умная RGB-лента с управлением через смартфон и голосовыми командами.'),
        ('Спот потолочный «Лофт» 3 лампы',   'osveshchenie',  4990,  None, True,  True,  False, 'Три регулируемых спота на трековой системе. Цоколь GU10. Стиль: лофт.'),
        # Хранение
        ('Стеллаж книжный «Библиотека»',      'hranenie',     9990, 12990, True,  False, True,  'Деревянный стеллаж с 5 полками. Размер 200×90×35 см. Несущая нагрузка 30 кг/полку.'),
        ('Корзина плетёная «Уют» с крышкой',  'hranenie',     1990,  None, False, True,  False, 'Корзина из натуральных материалов (морская трава) с крышкой. Размер 40×30×30 см.'),
        ('Органайзер для белья 12 ячеек',     'hranenie',     2490,  2990, False, False, True,  'Складной органайзер с 12 секциями для ящиков комода. Материал: оксфорд.'),
        ('Настенная полка «Минимализм» 80 см','hranenie',     3490,  None, True,  True,  False, 'Деревянная полка на металлических кронштейнах. Длина 80 см. Нагрузка 15 кг.'),
        ('Пуф-ящик для игрушек',              'hranenie',     5990,  7490, False, False, True,  'Мягкий пуф со скрытым отделением для хранения. Обивка — рогожка. 50×50×40 см.'),
        ('Набор стеклянных контейнеров 5 шт.','hranenie',     1990,  None, False, True,  False, 'Герметичные стеклянные контейнеры с бамбуковыми крышками: 0.5, 0.7, 1.0, 1.5, 2.0 л.'),
    ]

    for (name, cat_slug, price, old_price, is_featured,
         is_new, is_sale, desc) in products_seed:
        slug = slugify(name)
        if not Product.query.filter_by(slug=slug).first():
            cat = cat_map.get(cat_slug)
            if cat:
                p = Product(
                    name=name, slug=slug, category_id=cat.id,
                    price=price, old_price=old_price,
                    is_featured=is_featured, is_new=is_new, is_sale=is_sale,
                    description=desc,
                    full_description=desc + (
                        '\n\nТовар изготовлен по современным стандартам качества. '
                        'Соответствует всем требованиям ГОСТ. Гарантия производителя — 12 месяцев. '
                        'Доставка по всей России. Возможен самовывоз из любого магазина сети.'
                    ),
                    image=f'https://picsum.photos/seed/{slug[:12]}/400/300',
                    stock=50,
                )
                db.session.add(p)
    db.session.commit()

    # --- Новости (12 статей в 4 категориях — 3+ на каждую) ---
    admin_u = User.query.filter_by(username='admin').first()
    news_seed = [
        ('Тренды интерьера 2026: минимализм и экология',
         'Дизайн интерьера',
         'Рассказываем, что будет модным в 2026 году и как создать современный интерьер.',
         '''В 2026 году дизайнеры интерьера делают ставку на три ключевых тренда: минимализм, экологичность и многофункциональность.

**Минимализм** — это не пустые стены, а продуманное пространство. Каждый предмет мебели должен выполнять несколько функций: диван-трансформер, стол со встроенным хранением.

**Экологичность** выражается в натуральных материалах: дерево, лён, хлопок, шерсть. Покупатели всё чаще выбирают товары с сертификатом устойчивого производства.

**Многофункциональность** — ответ на рост городских квартир. Умная мебель, трансформеры, встроенные системы хранения.

Тёплые оттенки терракоты, оливкового и бежевого остаются базой палитры. Им на смену приходят приглушённые синие и глубокие зелёные тона.'''),

        ('Скандинавский стиль: секреты уюта',
         'Дизайн интерьера',
         'Хюгге, лагом и другие скандинавские концепции в вашем интерьере.',
         '''Скандинавский стиль завоевал сердца миллионов людей по всему миру. Его главные принципы: функциональность, простота и уют.

**Хюгге** (hygge) — датская философия уюта. Мягкие пледы, свечи, живые растения, деревянные детали и тёплый свет создают ощущение домашнего тепла.

**Лагом** (lagom) — шведский принцип «в самый раз». Ничего лишнего, но всё необходимое. Применительно к интерьеру: нейтральные тона, простые формы, качественные материалы.

В нашем каталоге вы найдёте всё необходимое для скандинавского интерьера: светлую деревянную мебель, льняной текстиль, лаконичный декор.'''),

        ('Биофилический дизайн: природа в доме',
         'Дизайн интерьера',
         'Как интегрировать природные элементы в городской интерьер.',
         '''Биофилический дизайн — это концепция, основанная на глубинной связи человека с природой.

Основные приёмы биофилического дизайна:
- Живые растения и вертикальные сады
- Натуральные материалы: камень, дерево, ротанг, джут
- Природные паттерны в текстиле и обоях
- Максимальное естественное освещение
- Земляная цветовая палитра: терракота, охра, сажень

Исследования показывают, что биофилические пространства снижают стресс, повышают концентрацию и улучшают качество сна.'''),

        ('Как выбрать правильное освещение',
         'Советы',
         'Освещение — главный инструмент создания атмосферы. Разбираемся в видах и сценариях.',
         '''Правильное освещение способно преобразить любое помещение. Ключевой принцип — многоуровневость.

**Общее освещение** создаёт базовый уровень света. Люстра или потолочные светильники.

**Задачное освещение** (рабочее) — настольные лампы, подсветка кухонного фартука, споты над рабочим столом.

**Акцентное освещение** выделяет детали: картины, полки, растения. Точечные светильники, гирлянды.

**Декоративное освещение** — свечи, ночники, гирлянды. Создаёт атмосферу уюта.

Температура света: 2700–3000 К (тёплый белый) — для жилых зон; 4000 К (нейтральный) — для кухни и рабочего места.'''),

        ('Организация хранения в маленькой квартире',
         'Советы',
         'Даже 30 кв. м можно организовать идеально. Делимся проверенными приёмами.',
         '''Маленькая квартира — не приговор, а творческий вызов. Вот проверенные приёмы:

**Вертикальное хранение.** Используйте высоту комнаты: полки до потолка, навесные органайзеры, магнитные полосы на кухне.

**Мебель-трансформер.** Диван с ящиками, кровать с подъёмным механизмом, обеденный стол-книжка.

**Зонирование.** Разделите пространство функционально: рабочая зона, зона отдыха, хранение.

**Правило «место для каждой вещи».** Любой предмет должен иметь фиксированное место. Это исключает хаос.

**Минимизация.** Избавьтесь от вещей, которыми не пользуетесь 6+ месяцев.'''),

        ('Уход за деревянной мебелью: советы экспертов',
         'Советы',
         'Деревянная мебель служит десятилетиями при правильном уходе.',
         '''Натуральное дерево — благородный и долговечный материал. Чтобы мебель сохраняла красоту годами, следуйте простым правилам.

**Влажность и температура.** Оптимальные условия: влажность 40–60%, температура 18–22 °C. Избегайте прямых солнечных лучей.

**Чистка.** Протирайте мягкой влажной (не мокрой!) тряпкой. Никакой химии — только специализированные средства для дерева.

**Полировка.** Раз в полгода наносите специальное масло или воск. Это питает древесину и создаёт защитный слой.

**Царапины.** Мелкие царапины маскируют восковыми мелками или тонирующими маслами в тон древесины.'''),

        ('Открытие нового магазина в Санкт-Петербурге',
         'Новости магазина',
         'Сеть «ДомашнийУют» открыла пятый магазин — в Северной столице!',
         '''Мы рады сообщить об открытии пятого магазина сети «ДомашнийУют» по адресу: Санкт-Петербург, Невский проспект, 147.

Новый магазин занимает площадь 1 200 кв. м на двух этажах. В нём представлены все категории товаров: мебель, текстиль, декор, кухня, освещение и системы хранения.

**Часы работы:** ежедневно с 10:00 до 21:00.

**Телефон:** +7 (812) 456-78-90.

В честь открытия — скидка 15% на всю мебель в течение первого месяца. Приходите!'''),

        ('Весенняя коллекция 2026: свежесть и цвет',
         'Новости магазина',
         'Встречайте новую коллекцию текстиля и декора — яркую, воздушную, весеннюю!',
         '''С приходом весны мы обновляем коллекцию! Новые позиции уже в продаже — в магазинах и на сайте.

**Текстиль весна-лето 2026:**
- Постельное бельё в пастельных тонах (мята, пыльная роза, лаванда)
- Лёгкие льняные шторы
- Плетёные корзины и боксы

**Декор:**
- Керамические вазы ручной работы
- Живые растения в керамических горшках
- Свечи с ароматами весенних цветов

Все новинки доступны по ссылке в разделе «Каталог → Новинки».'''),

        ('Программа лояльности: копите бонусы!',
         'Новости магазина',
         'Запускаем обновлённую бонусную программу для постоянных покупателей.',
         '''Дорогие покупатели! Мы запустили обновлённую программу лояльности «Домашний бонус».

**Как это работает:**
1. Зарегистрируйтесь на сайте
2. Совершайте покупки онлайн или в магазине
3. Получайте 5% от суммы покупки в виде бонусных рублей
4. Оплачивайте бонусами до 30% стоимости следующего заказа

**Уровни:**
- Стандарт (0–20 000 ₽) — 3%
- Серебро (20 000–100 000 ₽) — 5%
- Золото (100 000 ₽+) — 7%

Бонусы начисляются сразу после подтверждения заказа.'''),

        ('Итоги года: лучшие товары 2025',
         'Новости магазина',
         'Подводим итоги и называем хиты продаж уходящего года.',
         '''2025 год подошёл к концу, и мы готовы назвать хиты продаж!

**Топ-5 товаров года по версии покупателей:**

1. Диван-трансформер «Комфорт Плюс» — более 3 000 проданных штук
2. Постельный комплект «Прованс» — лидер в категории текстиль
3. Набор посуды «Гурмэ» — идеальный подарок
4. Нож шефский «Дамаск» — выбор настоящих кулинаров
5. Торшер «Скандинавия» — создаёт атмосферу в любой комнате

Спасибо, что выбираете «ДомашнийУют»! В 2026 году нас ждёт ещё больше новинок.'''),

        ('5 идей для уютной гостиной',
         'Советы',
         'Как создать идеальное пространство для отдыха и общения.',
         '''Гостиная — сердце дома. Вот 5 проверенных идей для создания уютного пространства.

**1. Мягкий диван — центр зоны отдыха.** Выбирайте просторный диван по размеру комнаты. Дополните его декоративными подушками и пледом.

**2. Ковёр задаёт зону.** Ковёр под журнальным столиком объединяет мебель в единую группу и добавляет уют.

**3. Многоуровневое освещение.** Торшер рядом с диваном, свечи на подносе, гирлянды — создают атмосферу.

**4. Живые растения.** Фикус, монстера, папоротник — живая зелень освежает пространство.

**5. Персональные детали.** Семейные фото, книги, любимые сувениры — это делает пространство «вашим».'''),

        ('Как правильно выбрать ковёр',
         'Советы',
         'Размер, материал, форма — всё о выборе ковра для разных помещений.',
         '''Ковёр — не просто напольное покрытие, это элемент дизайна и источник уюта.

**Размер.** Ковёр в гостиной должен быть достаточно большим, чтобы передние ножки дивана стояли на нём. Стандартный размер: 160×230 или 200×300 см.

**Материал.**
- Шерсть — тёплая, прочная, гипоаллергенная
- Хлопок — мягкий, моющийся, бюджетный
- Синтетика — практичная, износостойкая, лёгкая в уходе
- Натуральные (джут, сизаль) — экостиль, но жёсткие на ощупь

**Ворс.**
- Длинный ворс (40+ мм) — максимальный уют, сложнее чистить
- Короткий (до 10 мм) — практичнее, легче пылесосить
- Безворсовый — идеален для аллергиков'''),
    ]

    # Даты публикаций: с 03.12.2025 по 28.12.2025 (12 статей)
    news_dates = [
        datetime(2025, 12,  3),
        datetime(2025, 12,  5),
        datetime(2025, 12,  7),
        datetime(2025, 12,  9),
        datetime(2025, 12, 11),
        datetime(2025, 12, 13),
        datetime(2025, 12, 15),
        datetime(2025, 12, 17),
        datetime(2025, 12, 19),
        datetime(2025, 12, 21),
        datetime(2025, 12, 24),
        datetime(2025, 12, 28),
    ]

    for idx, (title, category, preview, content) in enumerate(news_seed):
        slug = slugify(title)
        if not NewsArticle.query.filter_by(slug=slug).first():
            pub_date = news_dates[idx] if idx < len(news_dates) else datetime(2025, 12, 28)
            art = NewsArticle(
                title=title, slug=slug, category=category,
                preview=preview, content=content,
                author_id=admin_u.id if admin_u else None,
                image=f'https://picsum.photos/seed/{slug[:10]}/800/400',
                views=0, is_published=True,
                created_at=pub_date,
            )
            db.session.add(art)
    db.session.commit()

    # --- Баннеры ---
    banners_seed = [
        ('Новая весенняя коллекция 2026', 'Обновите дом к новому сезону',
         '/catalog/tekstil', 'Смотреть коллекцию',
         'https://picsum.photos/seed/banner1spring/1200/500', 1),
        ('Скидки до 30% на мебель', 'Только до конца месяца! Лучшие цены года.',
         '/promotions', 'Получить скидку',
         'https://picsum.photos/seed/banner2sale/1200/500', 2),
        ('Освещение для вашего интерьера', 'Создайте идеальную атмосферу дома.',
         '/catalog/osveshchenie', 'Выбрать освещение',
         'https://picsum.photos/seed/banner3light/1200/500', 3),
    ]
    for title, sub, link, btn, img, order in banners_seed:
        if not Banner.query.filter_by(title=title).first():
            db.session.add(Banner(title=title, subtitle=sub, link=link,
                                  button_text=btn, image=img,
                                  is_active=True, order=order))
    db.session.commit()

    # --- Акции ---
    promos_seed = [
        ('Скидка 20% на всю мебель',
         'Обновите интерьер с выгодой! Акция распространяется на весь ассортимент мебели. Предложение ограничено по времени.',
         '−20%', 'MEBEL20', 'https://picsum.photos/seed/promo1mebel/600/400'),
        ('3 по цене 2 на текстиль',
         'Купите 3 предмета текстиля и заплатите только за 2! Подушки, пледы, постельное бельё — любые позиции.',
         '3=2', 'TEKSTIL3', 'https://picsum.photos/seed/promo2text/600/400'),
        ('Подарок при покупке от 10 000 ₽',
         'При покупке товаров на сумму от 10 000 рублей вы получаете подарок на выбор: ароматическую свечу или набор полотенец.',
         'Подарок', None, 'https://picsum.photos/seed/promo3gift/600/400'),
        ('Бесплатная доставка',
         'Бесплатная доставка на все заказы от 5 000 рублей по Москве и Санкт-Петербургу. По России — от 10 000 рублей.',
         '0 ₽', None, 'https://picsum.photos/seed/promo4delivery/600/400'),
        ('−15% для новых покупателей',
         'Зарегистрируйтесь на сайте и получите скидку 15% на первый заказ. Используйте промокод при оформлении.',
         '−15%', 'NEW15', 'https://picsum.photos/seed/promo5new/600/400'),
        ('Распродажа прошлого сезона — до 50%',
         'Товары из коллекции осень-зима 2025 продаются со скидками до 50%. Успейте купить!',
         'до −50%', None, 'https://picsum.photos/seed/promo6season/600/400'),
    ]
    for title, desc, discount, code, img in promos_seed:
        if not Promotion.query.filter_by(title=title).first():
            db.session.add(Promotion(title=title, description=desc,
                                     discount_text=discount, promo_code=code,
                                     image=img, is_active=True))
    db.session.commit()

    print('[OK] База данных инициализирована!')
    print('Uchotnyye zapisi:')
    print('  admin   / admin123    - administrator')
    print('  manager / manager123  - menedzher')
    print('  user1   / user1234    - pokupatel')
    print('  user2   / user5678    - pokupatel')


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Автоматическое наполнение БД при первом запуске
        if not User.query.first():
            seed_database()
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
