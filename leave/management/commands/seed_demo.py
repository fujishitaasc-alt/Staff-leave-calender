import secrets
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from leave.models import Staff, Leave, LeaveType


class Command(BaseCommand):
    help = "DEMO=1 のときだけ、架空職員13名とサンプル予定を作成します"

    def handle(self, *args, **options):
        if (
            not settings.DEMO
            or settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3"
            or str(settings.DATABASES["default"]["NAME"])
            != str(settings.BASE_DIR / "demo.sqlite3")
        ):
            raise CommandError(
                "DEMO=1 かつ DATABASE_URL 未設定の専用SQLiteで実行してください"
            )
        kind, _ = LeaveType.objects.get_or_create(name="休暇")
        names = [
            "青葉 はる",
            "若草 そら",
            "小鳥 ゆう",
            "朝露 りん",
            "木陰 なつ",
            "花園 かい",
            "月野 あき",
            "風見 みお",
            "星川 せい",
            "虹丘 れい",
            "白雲 まき",
            "春風 なお",
            "水辺 とわ",
        ]
        for i, name in enumerate(names):
            u, created = Staff.objects.get_or_create(
                username=f"demo{i+1:02}",
                defaults={
                    "name": name,
                    "role": "PT" if i < 10 else "ASSISTANT",
                    "is_staff": i == 0,
                    "is_superuser": i == 0,
                },
            )
            if created:
                password = secrets.token_urlsafe(15)
                u.set_password(password)
                u.save()
                self.stdout.write(f"{u.username} 初回パスワード: {password}")
            if i < 6:
                Leave.objects.get_or_create(
                    staff=u,
                    date=timezone.localdate() + timedelta(days=i // 2),
                    defaults={"kind": ["FULL", "AM", "PM"][i % 3], "leave_type": kind},
                )
        self.stdout.write(
            "既存ユーザーのパスワードは変更しません。出力したパスワードは安全に管理してください。"
        )
