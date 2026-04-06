from decimal import Decimal
from django.db import transaction

from .models import Order, OrderItem


class OrderService:
    @staticmethod
    @transaction.atomic
    def create_order(user, goods_objs, promo=None, discount=Decimal("0.00")):
        order = Order.objects.create(user=user, promo_code=promo)

        total_price = Decimal("0.00")
        total_discount = Decimal("0.00")

        for item in goods_objs:
            good = item["good"]
            quantity = item["quantity"]

            line_price = good.price * quantity
            line_discount = line_price * discount
            line_total = line_price - line_discount

            OrderItem.objects.create(
                order=order,
                good=good,
                quantity=quantity,
                price=good.price,
                discount=discount,
                total=line_total,
            )

            total_price += line_price
            total_discount += line_discount

        order.total_price = total_price
        order.total_discount = total_discount
        order.save()

        if promo:
            promo.used_count += 1
            promo.save()

        return order