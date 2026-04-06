from django.db import models


class TimeStampedModel(models.Model):
    """
    Абстрактная модель, добавляющая поля для отслеживания времени создания и обновления объектов.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    """
    Модель категории товаров.

    Атрибуты:
        name (str): Название категории.
    """
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Good(TimeStampedModel):
    """
    Модель товара.

    Атрибуты:
        name (str): Название товара.
        price (Decimal): Цена товара.
        category (ForeignKey): Ссылка на категорию товара.
        exclude_from_promo (bool): Флаг, указывающий, участвует ли товар в промоакциях.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, null=True, blank=True
    )
    exclude_from_promo = models.BooleanField(default=False)

    def __str__(self):
        return self.name