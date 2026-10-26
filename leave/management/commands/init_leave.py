from django.core.management.base import BaseCommand
from leave.models import LeaveType, Threshold, ROLES


class Command(BaseCommand):
    help = "休暇種別と職種別の未設定注意基準を作成（再実行可）"

    def handle(self, *args, **options):
        LeaveType.objects.get_or_create(name="休暇")
        for role, _ in ROLES:
            Threshold.objects.get_or_create(role=role)
        self.stdout.write("初期設定を確認しました。既存の注意基準は変更していません。")
