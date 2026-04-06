from rest_framework import generics
from .models import Order
from .serializers import OrderSerializer


class OrderCreateAPIView(generics.CreateAPIView):
    """
    APIView для создания нового заказа.

    Метод:
        POST: Создает заказ с указанием пользователя, товаров и необязательного промокода.

    Атрибуты:
        queryset (QuerySet): Все объекты заказов.
        serializer_class (Serializer): Сериализатор для валидации и создания заказа (OrderSerializer).

    Пример запроса:
        POST /api/orders/
        {
            "user_id": 1,
            "goods": [
                {"good_id": 1, "quantity": 2},
                {"good_id": 3, "quantity": 1}
            ],
            "promo_code": "SUMMER2025"
        }

    Пример успешного ответа:
        {
            "user_id": 1,
            "order_id": 1,
            "goods": [
                {"good_id": 1, "quantity": 2, "price": 100, "discount": 0.1, "total": 180},
                {"good_id": 3, "quantity": 1, "price": 50, "discount": 0.1, "total": 45}
            ],
            "price": 250,
            "discount": 0.1,
            "total": 225
        }
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer