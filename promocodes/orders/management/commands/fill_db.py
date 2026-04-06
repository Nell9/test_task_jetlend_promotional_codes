from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from goods.models import Category, Good
from orders.models import Order, OrderItem, PromoCode

User = get_user_model()


class Command(BaseCommand):
    help = "Заполняет БД тестовыми данными: пользователи, категории, товары, промокоды, заказы"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("🌱 Начинаю заполнение БД...")

        # -----------------------------
        # 1. Пользователи
        # -----------------------------
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password("admin123")
        admin.save()

        user1, created = User.objects.get_or_create(
            username="user1",
            defaults={
                "email": "user1@example.com",
            },
        )
        user1.set_password("user123")
        user1.save()

        user2, created = User.objects.get_or_create(
            username="user2",
            defaults={
                "email": "user2@example.com",
            },
        )
        user2.set_password("user123")
        user2.save()

        self.stdout.write(self.style.SUCCESS("👥 Пользователи созданы."))

        # -----------------------------
        # 2. Категории
        # -----------------------------
        electronics, _ = Category.objects.get_or_create(name="Электроника")
        accessories, _ = Category.objects.get_or_create(name="Аксессуары")
        clothes, _ = Category.objects.get_or_create(name="Одежда")
        books, _ = Category.objects.get_or_create(name="Книги")

        self.stdout.write(self.style.SUCCESS("📂 Категории созданы."))

        # -----------------------------
        # 3. Товары
        # -----------------------------
        laptop, _ = Good.objects.get_or_create(
            name="Ноутбук",
            defaults={
                "price": Decimal("50000.00"),
                "category": electronics,
                "exclude_from_promo": False,
            },
        )

        mouse, _ = Good.objects.get_or_create(
            name="Беспроводная мышь",
            defaults={
                "price": Decimal("1500.00"),
                "category": accessories,
                "exclude_from_promo": False,
            },
        )

        keyboard, _ = Good.objects.get_or_create(
            name="Клавиатура",
            defaults={
                "price": Decimal("3000.00"),
                "category": accessories,
                "exclude_from_promo": False,
            },
        )

        tshirt, _ = Good.objects.get_or_create(
            name="Футболка с логотипом",
            defaults={
                "price": Decimal("1000.00"),
                "category": clothes,
                "exclude_from_promo": True,
            },
        )

        book, _ = Good.objects.get_or_create(
            name="Книга по Django",
            defaults={
                "price": Decimal("2500.00"),
                "category": books,
                "exclude_from_promo": False,
            },
        )

        self.stdout.write(self.style.SUCCESS("📦 Товары созданы."))

        # -----------------------------
        # 4. Промокоды
        # -----------------------------
        future_date = timezone.now() + timedelta(days=30)
        expired_date = timezone.now() - timedelta(days=5)

        sale10, _ = PromoCode.objects.get_or_create(
            code="SALE10",
            defaults={
                "discount": Decimal("0.10"),
                "max_uses": 100,
                "used_count": 0,
                "expiry_date": future_date,
            },
        )
        sale10.allowed_categories.set([electronics, accessories])

        welcome15, _ = PromoCode.objects.get_or_create(
            code="WELCOME15",
            defaults={
                "discount": Decimal("0.15"),
                "max_uses": 50,
                "used_count": 0,
                "expiry_date": future_date,
            },
        )
        welcome15.allowed_categories.set([books, accessories])

        expired_code, _ = PromoCode.objects.get_or_create(
            code="EXPIRED20",
            defaults={
                "discount": Decimal("0.20"),
                "max_uses": 5,
                "used_count": 0,
                "expiry_date": expired_date,
            },
        )
        expired_code.allowed_categories.set([])

        self.stdout.write(self.style.SUCCESS("🎟️ Промокоды созданы."))

        # -----------------------------
        # 5. Заказ user1 с промокодом SALE10
        # -----------------------------
        if not Order.objects.filter(user=user1, promo_code=sale10).exists():
            order1 = Order.objects.create(
                user=user1,
                promo_code=sale10,
            )

            item1_total = Decimal("1") * laptop.price * (Decimal("1.00") - sale10.discount)
            item2_total = Decimal("2") * mouse.price * (Decimal("1.00") - sale10.discount)

            OrderItem.objects.create(
                order=order1,
                good=laptop,
                quantity=1,
                price=laptop.price,
                discount=sale10.discount,
                total=item1_total,
            )

            OrderItem.objects.create(
                order=order1,
                good=mouse,
                quantity=2,
                price=mouse.price,
                discount=sale10.discount,
                total=item2_total,
            )

            order1.total_price = laptop.price + (mouse.price * 2)
            order1.total_discount = order1.total_price * sale10.discount
            order1.save()

            sale10.used_count += 1
            sale10.save()

            self.stdout.write(self.style.SUCCESS("🛒 Заказ user1 с промокодом SALE10 создан."))

        # -----------------------------
        # 6. Заказ user2 без промокода
        # -----------------------------
        if not Order.objects.filter(user=user2, promo_code__isnull=True).exists():
            order2 = Order.objects.create(
                user=user2,
                promo_code=None,
            )

            item_total = tshirt.price * 3

            OrderItem.objects.create(
                order=order2,
                good=tshirt,
                quantity=3,
                price=tshirt.price,
                discount=Decimal("0.00"),
                total=item_total,
            )

            order2.total_price = item_total
            order2.total_discount = Decimal("0.00")
            order2.save()

            self.stdout.write(self.style.SUCCESS("🛒 Заказ user2 без промокода создан."))

        # -----------------------------
        # 7. Ещё один заказ user2 с обычными товарами
        # -----------------------------
        if not Order.objects.filter(user=user2, promo_code=welcome15).exists():
            order3 = Order.objects.create(
                user=user2,
                promo_code=welcome15,
            )

            item1_total = keyboard.price * 1 * (Decimal("1.00") - welcome15.discount)
            item2_total = book.price * 1 * (Decimal("1.00") - welcome15.discount)

            OrderItem.objects.create(
                order=order3,
                good=keyboard,
                quantity=1,
                price=keyboard.price,
                discount=welcome15.discount,
                total=item1_total,
            )

            OrderItem.objects.create(
                order=order3,
                good=book,
                quantity=1,
                price=book.price,
                discount=welcome15.discount,
                total=item2_total,
            )

            order3.total_price = keyboard.price + book.price
            order3.total_discount = order3.total_price * welcome15.discount
            order3.save()

            welcome15.used_count += 1
            welcome15.save()

            self.stdout.write(self.style.SUCCESS("🛒 Заказ user2 с промокодом WELCOME15 создан."))

        self.stdout.write(self.style.SUCCESS("✅ БД успешно заполнена тестовыми данными!"))