import secrets
from decimal import Decimal
from extensions import db
from models.models import Admin, Category, Customer, Order, OrderItem, Product, ShippingRate, utcnow
from utils.helpers import EGYPT_GOVERNORATES, slugify

DEMO_CATEGORIES = [
    ("عناية بالبشرة", "روتينات يومية مختارة للعناية بالبشرة"),
    ("عطور", "روائح أنيقة لكل يوم ومناسبة"),
    ("منزل وديكور", "تفاصيل صغيرة تجعل البيت أجمل"),
]
DEMO_PRODUCTS = [
    ("سيروم فيتامين سي", "عناية بالبشرة", "تركيبة خفيفة تمنح البشرة إشراقة وملمساً ناعماً.", "EGP-VITC-30", "680.00", 24, True),
    ("مرطب يومي بالصبار", "عناية بالبشرة", "ترطيب مريح للاستخدام اليومي بلمسة غير دهنية.", "EGP-ALOE-01", "420.00", 32, True),
    ("عطر نسيم النيل", "عطور", "مزيج منعش مستوحى من أمسيات القاهرة الهادئة.", "EGP-NILE-50", "1250.00", 14, True),
    ("شمعة قطن ومسك", "منزل وديكور", "شمعة معطرة بعبير قطني دافئ لوقت الاسترخاء.", "EGP-CNDL-02", "390.00", 18, False),
    ("زيت شعر مغذٍ", "عناية بالبشرة", "مزيج زيوت نباتية للعناية بالأطراف الجافة.", "EGP-HAIR-08", "540.00", 20, True),
    ("حقيبة هدايا ريجويا", "منزل وديكور", "تغليف أنيق مناسب للهدايا والمناسبات.", "EGP-GIFT-01", "160.00", 50, False),
]


def seed_database(app):
    with app.app_context():
        db.create_all()
        fresh_install = not any((Admin.query.count(), Customer.query.count(), Category.query.count(), Product.query.count(), Order.query.count(), ShippingRate.query.count()))

        admin_email = app.config["ADMIN_EMAIL"]
        admin = Admin.query.filter_by(email=admin_email).first()
        if not admin:
            admin = Admin.query.order_by(Admin.id).first()
            if admin:
                admin.email = admin_email
        configured_password = app.config.get("ADMIN_PASSWORD")
        if not admin:
            if not configured_password:
                configured_password = secrets.token_urlsafe(24)
                app.logger.warning("Generated one-time Rijoya admin password for %s: %s", admin_email, configured_password)
            admin = Admin(email=admin_email)
            db.session.add(admin)
        if configured_password:
            admin.set_password(configured_password)

        categories = {category.name: category for category in Category.query.all()}
        if not categories:
            for name, description in DEMO_CATEGORIES:
                category = Category(name=name, slug=slugify(name), description=description)
                db.session.add(category)
                categories[name] = category
            db.session.flush()
            for name, category_name, description, sku, price, stock, featured in DEMO_PRODUCTS:
                db.session.add(Product(
                    category_id=categories[category_name].id,
                    name=name, slug=slugify(name), description=description,
                    price=Decimal(price), stock=stock, sku=sku,
                    is_active=True, is_featured=featured,
                ))
            db.session.flush()

        if ShippingRate.query.count() == 0:
            for gov in EGYPT_GOVERNORATES:
                fee = Decimal("65.00") if gov in {"القاهرة", "الجيزة"} else Decimal("85.00")
                db.session.add(ShippingRate(governorate=gov, city="", area="", fee=fee))

        # A clearly fictional example order is useful for admin review, but only on an empty first install.
        if fresh_install and Order.query.count() == 0:
            customer = Customer(
                full_name="عميل تجريبي", email="sample.customer@rijoya.local",
                phone="+201000000000",
            )
            customer.set_password(secrets.token_urlsafe(32))
            db.session.add(customer)
            db.session.flush()
            product = Product.query.filter_by(sku="EGP-VITC-30").first()
            if product:
                created_at = utcnow()
                order = Order(
                    order_number="PENDING", customer=customer,
                    customer_name=customer.full_name, email=customer.email,
                    phone=customer.phone, governorate="القاهرة", city="القاهرة",
                    area="المعادي", address="عنوان تجريبي — يُرجى تجاهله",
                    notes="طلب تجريبي لإنشاء معاينة داخل لوحة الإدارة.",
                    subtotal=product.price, shipping_fee=Decimal("65.00"),
                    total=product.price + Decimal("65.00"), payment_method="cod",
                    status="delivered", created_at=created_at,
                )
                db.session.add(order)
                db.session.flush()
                order.order_number = f"ORD-{created_at:%Y%m%d}-{order.id:06d}"
                db.session.add(OrderItem(
                    order=order, product_id=product.id, product_name=product.name,
                    sku=product.sku, unit_price=product.price, quantity=1,
                    line_total=product.price,
                ))
        db.session.commit()
