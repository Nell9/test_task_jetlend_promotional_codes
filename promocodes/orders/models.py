from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from goods.models import Category, Good

User = get_user_model()


class TimeStampedModel(models.Model):
    """
    Абстрактная модель, добавляющая поля временных меток для всех моделей.

    Поля:
        created_at (DateTimeField): Время создания записи.
        updated_at (DateTimeField): Время последнего обновления записи.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PromoCode(TimeStampedModel):
    """
    Модель промокода для применения скидок к товарам.

    Поля:
        code (CharField): Уникальный код промокода.
        discount (DecimalField): Скидка в виде десятичного числа (0.1 = 10%).
        max_uses (PositiveIntegerField): Максимальное число применений промокода.
        used_count (PositiveIntegerField): Сколько раз промокод уже использован.
        expiry_date (DateTimeField): Дата и время окончания действия промокода.
        allowed_categories (ManyToManyField): Категории товаров, к которым можно
            применять промокод.
    """

    code = models.CharField(max_length=50, unique=True)
    discount = models.DecimalField(max_digits=4, decimal_places=2)
    max_uses = models.PositiveIntegerField()
    used_count = models.PositiveIntegerField(default=0)
    expiry_date = models.DateTimeField()
    allowed_categories = models.ManyToManyField(Category, blank=True)

    def is_valid(self, user, goods):
        """
        Проверяет валидность промокода для пользователя и списка товаров.

        Args:
            user (User): Пользователь, который применяет промокод.
            goods (list[Good]): Список товаров, к которым применяется промокод.

        Returns:
            tuple: (bool, str) — True и пустая строка, если промокод валиден,
            иначе False и сообщение с причиной недействительности.
        """
        now = timezone.now()
        if now > self.expiry_date:
            return False, "Промокод просрочен"
        if self.used_count >= self.max_uses:
            return False, "Промокод использован максимально"
        if self.order_set.filter(user=user).exists():
            return False, "Пользователь уже использовал этот промокод"

        allowed_cats = set(self.allowed_categories.all())
        for g in goods:
            if g.exclude_from_promo:
                return False, f"Товар {g.name} не участвует в промо-акции"
            if allowed_cats and g.category not in allowed_cats:
                return False, f"Товар {g.name} не подходит по категории"

        return True, ""


class Order(TimeStampedModel):
    """
    Модель заказа, содержащего один или несколько товаров и опциональный
    промокод.

    Поля:
        user (ForeignKey): Пользователь, создавший заказ.
        promo_code (ForeignKey): Применённый промокод (опционально).
        total_price (DecimalField): Общая стоимость заказа без скидки.
        total_discount (DecimalField): Общая сумма скидки по заказу.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    promo_code = models.ForeignKey(
        PromoCode, on_delete=models.SET_NULL, null=True, blank=True
    )
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"Order #{self.id} by {self.user}"


class OrderItem(TimeStampedModel):
    """
    Модель позиции заказа — отдельный товар, включённый в заказ.

    Поля:
        order (ForeignKey): Заказ, к которому относится позиция.
        good (ForeignKey): Товар.
        quantity (PositiveIntegerField): Количество единиц товара.
        price (DecimalField): Цена за единицу товара.
        discount (DecimalField): Процент скидки, применённой к товару.
        total (DecimalField): Итоговая стоимость позиции с учётом скидки.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    good = models.ForeignKey(Good, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.good.name} for Order #{self.order.id}"