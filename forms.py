from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional


class LoginForm(FlaskForm):
    email = StringField("البريد الإلكتروني", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("كلمة المرور", validators=[DataRequired(), Length(min=8, max=128)])
    remember = BooleanField("تذكرني")
    submit = SubmitField("تسجيل الدخول")


class RegisterForm(FlaskForm):
    full_name = StringField("الاسم الكامل", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("البريد الإلكتروني", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("رقم الهاتف", validators=[DataRequired(), Length(min=8, max=30)])
    password = PasswordField("كلمة المرور", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField("تأكيد كلمة المرور", validators=[DataRequired(), EqualTo("password", message="كلمتا المرور غير متطابقتين.")])
    submit = SubmitField("إنشاء حساب")


class CheckoutForm(FlaskForm):
    full_name = StringField("الاسم الكامل", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("البريد الإلكتروني", validators=[Optional(), Email(), Length(max=255)])
    phone = StringField("رقم الهاتف", validators=[DataRequired(), Length(min=8, max=30)])
    governorate = SelectField("المحافظة", validators=[DataRequired()])
    city = StringField("المدينة", validators=[Optional(), Length(max=100)])
    area = StringField("المنطقة", validators=[Optional(), Length(max=100)])
    address = StringField("العنوان بالتفصيل", validators=[DataRequired(), Length(min=5, max=500)])
    notes = TextAreaField("ملاحظات للتوصيل", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("تأكيد الطلب — الدفع عند الاستلام")


class ProductForm(FlaskForm):
    name = StringField("اسم المنتج", validators=[DataRequired(), Length(max=160)])
    category_id = SelectField("التصنيف", coerce=int, validators=[Optional()])
    sku = StringField("رمز SKU", validators=[DataRequired(), Length(max=60)])
    description = TextAreaField("الوصف", validators=[Optional(), Length(max=5000)])
    price = DecimalField("السعر بالجنيه", places=2, validators=[DataRequired(), NumberRange(min=0)])
    compare_at_price = DecimalField("السعر قبل الخصم", places=2, validators=[Optional(), NumberRange(min=0)])
    stock = IntegerField("المخزون", validators=[DataRequired(), NumberRange(min=0)])
    image = FileField("صورة المنتج", validators=[FileAllowed(["jpg", "jpeg", "png", "webp", "gif"], "صيغة الصورة غير مدعومة.")])
    is_active = BooleanField("ظاهر في المتجر", default=True)
    is_featured = BooleanField("منتج مميز")
    submit = SubmitField("حفظ المنتج")


class CategoryForm(FlaskForm):
    name = StringField("اسم التصنيف", validators=[DataRequired(), Length(max=100)])
    description = StringField("وصف مختصر", validators=[Optional(), Length(max=500)])
    image = FileField("صورة التصنيف", validators=[FileAllowed(["jpg", "jpeg", "png", "webp", "gif"], "صيغة الصورة غير مدعومة.")])
    is_active = BooleanField("ظاهر في المتجر", default=True)
    submit = SubmitField("حفظ التصنيف")
