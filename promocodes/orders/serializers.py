from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from goods.models import Good
from .models import Order, OrderItem, PromoCode
from .services import OrderService

User = get_user_model()


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Сериализатор позиции заказа.

    Используется для отображения товаров, входящих в заказ.

    Поля:
        good_id (int): Идентификатор товара.
        quantity (int): Количество товара.
        price (Decimal): Цена за единицу товара.
        discount (Decimal): Размер скидки для позиции.
        total (Decimal): Итоговая стоимость позиции с учётом скидки.
    """

    good_id = serializers.IntegerField(source="good.id", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["good_id", "quantity", "price", "discount", "total"]


class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор заказа.

    Отвечает за:
    - валидацию входных данных;
    - получение пользователя, товаров и промокода;
    - передачу подготовленных данных в сервис создания заказа.

    Входные поля:
        user_id (int): Идентификатор пользователя.
        goods (list[dict]): Список товаров и их количества.
        promo_code (str): Промокод, если он указан.

    Выходные поля:
        items (list): Список позиций заказа.
        price (Decimal): Общая стоимость заказа без скидки.
        discount (Decimal): Общая сумма скидки.
        total (Decimal): Итоговая стоимость заказа после скидки.
    """

    user_id = serializers.IntegerField(write_only=True)
    goods = serializers.ListField(child=serializers.DictField(), write_only=True)
    promo_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    items = OrderItemSerializer(read_only=True, many=True)
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        source="total_price",
        read_only=True,
    )
    discount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        source="total_discount",
        read_only=True,
    )
    total = serializers.SerializerMethodField(read_only=True)

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

    def get_total(self, obj):
        """
        Возвращает итоговую стоимость заказа после вычета скидки.

        Args:
            obj (Order): Объект заказа.

        Returns:
            Decimal: Итоговая сумма заказа.
        """
        return obj.total_price - obj.total_discount

    def _get_user(self, user_id):
        """
        Получает пользователя по идентификатору.

        Args:
            user_id (int): Идентификатор пользователя.

        Returns:
            User: Найденный пользователь.

        Raises:
            serializers.ValidationError: Если пользователь не найден.
        """
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist as err:
            raise serializers.ValidationError(
                {"user_id": "Пользователь не найден"}
            ) from err

    def _get_good(self, good_id):
        """
        Получает товар по идентификатору.

        Args:
            good_id (int): Идентификатор товара.

        Returns:
            Good: Найденный товар.

        Raises:
            serializers.ValidationError: Если товар не найден.
        """
        try:
            return Good.objects.get(id=good_id)
        except Good.DoesNotExist as err:
            raise serializers.ValidationError(
                {"goods": f"Товар с id {good_id} не найден"}
            ) from err

    def _get_goods_objects(self, goods_data):
        """
        Преобразует входной список товаров в список объектов Good с количеством.

        Args:
            goods_data (list[dict]): Список словарей вида:
                {
                    "good_id": int,
                    "quantity": int
                }

        Returns:
            list[dict]: Список словарей вида:
                {
                    "good": <Good>,
                    "quantity": int
                }

        Raises:
            serializers.ValidationError: Если формат данных неверный,
            список товаров пустой или товар не найден.
        """
        if not goods_data:
            raise serializers.ValidationError(
                {"goods": "Список товаров не может быть пустым"}
            )

        goods_objs = []

        for item in goods_data:
            if "good_id" not in item or "quantity" not in item:
                raise serializers.ValidationError(
                    {"goods": "Неверный формат данных товара"}
                )

            quantity = item["quantity"]
            if not isinstance(quantity, int) or quantity <= 0:
                raise serializers.ValidationError(
                    {"goods": "Количество товара должно быть положительным целым числом"}
                )

            good = self._get_good(item["good_id"])
            goods_objs.append({
                "good": good,
                "quantity": quantity,
            })

        return goods_objs

    def _get_promo(self, promo_code_str, user, goods_objs):
        """
        Получает и валидирует промокод.

        Args:
            promo_code_str (str | None): Строковое значение промокода.
            user (User): Пользователь, оформляющий заказ.
            goods_objs (list[dict]): Список товаров заказа.

        Returns:
            tuple[PromoCode | None, Decimal]: Промокод и размер скидки.

        Raises:
            serializers.ValidationError: Если промокод не существует
            или не подходит для заказа.
        """
        if not promo_code_str:
            return None, Decimal("0.00")

        try:
            promo = PromoCode.objects.get(code=promo_code_str)
        except PromoCode.DoesNotExist as err:
            raise serializers.ValidationError(
                {"promo_code": "Промокод не существует"}
            ) from err

        valid, msg = promo.is_valid(user, [item["good"] for item in goods_objs])
        if not valid:
            raise serializers.ValidationError({"promo_code": msg})

        return promo, promo.discount

    def validate(self, attrs):
        """
        Выполняет кросс-полевую валидацию заказа.

        Логика:
        1. Получает пользователя.
        2. Получает объекты товаров.
        3. Получает и проверяет промокод.
        4. Сохраняет подготовленные данные в attrs для метода create().

        Args:
            attrs (dict): Входные данные после базовой валидации полей.

        Returns:
            dict: Обновлённые атрибуты с подготовленными объектами.
        """
        user = self._get_user(attrs["user_id"])
        goods_objs = self._get_goods_objects(attrs["goods"])
        promo, discount = self._get_promo(attrs.get("promo_code"), user, goods_objs)

        attrs["validated_user"] = user
        attrs["validated_goods"] = goods_objs
        attrs["validated_promo"] = promo
        attrs["validated_discount"] = discount
        return attrs

    def create(self, validated_data):
        """
        Создаёт заказ через сервисный слой.

        Args:
            validated_data (dict): Провалидированные данные заказа.

        Returns:
            Order: Созданный объект заказа.
        """
        return OrderService.create_order(
            user=validated_data["validated_user"],
            goods_objs=validated_data["validated_goods"],
            promo=validated_data["validated_promo"],
            discount=validated_data["validated_discount"],
        )
    