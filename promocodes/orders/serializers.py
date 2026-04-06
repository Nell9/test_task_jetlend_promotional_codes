from django.contrib.auth import get_user_model
from rest_framework import serializers

from goods.models import Good
from .models import Order, OrderItem, PromoCode

User = get_user_model()


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Сериализатор для отдельной позиции заказа.

    Поля:
        good_id (int): Идентификатор товара.
        price (Decimal): Цена за единицу товара.
        discount (Decimal): Скидка, применённая к позиции.
        total (Decimal): Итоговая стоимость позиции с учётом скидки.
    """
    good_id = serializers.IntegerField(source="good.id")
    price = serializers.DecimalField(
        source="price", max_digits=10, decimal_places=2
    )
    discount = serializers.DecimalField(
        source="discount", max_digits=4, decimal_places=2
    )
    total = serializers.DecimalField(
        source="total", max_digits=12, decimal_places=2
    )

    class Meta:
        model = OrderItem
        fields = ["good_id", "quantity", "price", "discount", "total"]


class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор заказа с поддержкой промокодов.

    Поля:
        user_id (int): Идентификатор пользователя.
        goods (list[dict]): Список товаров с полями 'good_id' и 'quantity'.
        promo_code (str, optional): Код промокода.
        items (list[OrderItemSerializer]): Список позиций заказа.
        price (Decimal): Общая стоимость заказа без скидки.
        discount (Decimal): Суммарная скидка по заказу.
        total (Decimal): Итоговая стоимость заказа с учётом скидки.
    """
    user_id = serializers.IntegerField()
    goods = serializers.ListField(
        child=serializers.DictField(), write_only=True
    )
    promo_code = serializers.CharField(required=False, allow_blank=True)
    items = OrderItemSerializer(read_only=True, many=True)
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, source="total_price", read_only=True
    )
    discount = serializers.DecimalField(
        max_digits=4, decimal_places=2, source="total_discount", read_only=True
    )
    total = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Order
        fields = [
            "user_id",
            "goods",
            "promo_code",
            "items",
            "price",
            "discount",
            "total",
        ]

    def get_user(self, user_id):
        """
        Получение объекта пользователя по user_id.

        Args:
            user_id (int): Идентификатор пользователя.

        Returns:
            User: Объект пользователя.

        Raises:
            ValidationError: Если пользователь с указанным id не найден.
        """
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist as err:
            raise serializers.ValidationError(
                {"user_id": "Пользователь не найден"}
            ) from err

    def get_goods_objects(self, goods_data):
        """
        Получение объектов товаров из данных запроса.

        Args:
            goods_data (list[dict]): Список словарей с 'good_id' и 'quantity'.

        Returns:
            list[dict]: Список словарей с объектом Good и количеством.

        Raises:
            ValidationError: Если один из товаров не найден.
        """
        goods_objs = []
        for g in goods_data:
            try:
                good = Good.objects.get(id=g["good_id"])
                goods_objs.append({"good": good, "quantity": g["quantity"]})
            except Good.DoesNotExist as err:
                raise serializers.ValidationError(
                    {"goods": f"Товар с id {g['good_id']} не найден"}
                ) from err
        return goods_objs

    def validate_promo_code(self, promo_code_str, user, goods_objs):
        """
        Валидация и применение промокода к заказу.

        Args:
            promo_code_str (str): Код промокода.
            user (User): Пользователь, создающий заказ.
            goods_objs (list[dict]): Список товаров с объектами Good и количеством.

        Returns:
            tuple: (PromoCode или None, Decimal) — объект промокода и скидка.

        Raises:
            ValidationError: Если промокод не существует или невалиден.
        """
        if not promo_code_str:
            return None, 0

        try:
            promo = PromoCode.objects.get(code=promo_code_str)
        except PromoCode.DoesNotExist as err:
            raise serializers.ValidationError(
                {"promo_code": "Промокод не существует"}
            ) from err

        valid, msg = promo.is_valid(user, [g["good"] for g in goods_objs])
        if not valid:
            raise serializers.ValidationError({"promo_code": msg})

        promo.used_count += 1
        promo.save()
        return promo, promo.discount

    def calculate_order_items(self, order, goods_objs, discount):
        """
        Создание позиций заказа и вычисление общей стоимости и скидки.

        Args:
            order (Order): Созданный объект заказа.
            goods_objs (list[dict]): Список товаров с объектами Good и количеством.
            discount (Decimal): Скидка на заказ (например, 0.1 = 10%).

        Returns:
            tuple: (total_price, total_discount) — сумма цен и сумма скидки.
        """
        total_price = 0
        total_discount = 0

        for g in goods_objs:
            price = g["good"].price * g["quantity"]
            disc = price * discount
            total = price - disc

            OrderItem.objects.create(
                order=order,
                good=g["good"],
                quantity=g["quantity"],
                price=g["good"].price,
                discount=discount,
                total=total,
            )

            total_price += price
            total_discount += disc

        return total_price, total_discount

    def create(self, validated_data):
        """
        Создание заказа вместе с позициями и применением промокода.

        Args:
            validated_data (dict): Валидированные данные запроса.

        Returns:
            Order: Созданный объект заказа с позициями и скидкой.
        """
        user = self.get_user(validated_data["user_id"])
        goods_data = validated_data.pop("goods")
        promo_code_str = validated_data.get("promo_code", None)

        goods_objs = self.get_goods_objects(goods_data)
        promo, discount = self.validate_promo_code(
            promo_code_str, user, goods_objs
        )

        order = Order.objects.create(user=user, promo_code=promo)
        total_price, total_discount = self.calculate_order_items(
            order, goods_objs, discount
        )

        order.total_price = total_price
        order.total_discount = total_discount
        order.save()
        return order