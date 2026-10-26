from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from datetime import time

ROLES = [("PT", "理学療法士"), ("ASSISTANT", "リハビリ助手")]


class Staff(AbstractUser):
    name = models.CharField("職員名", max_length=80)
    role = models.CharField("職種", max_length=12, choices=ROLES, default="PT")

    class Meta(AbstractUser.Meta):
        verbose_name = "職員"
        verbose_name_plural = "職員"

    def __str__(self):
        return self.name or self.username


class LeaveType(models.Model):
    name = models.CharField("休暇種別", max_length=40, unique=True, default="休暇")
    active = models.BooleanField("利用可能", default=True)

    class Meta:
        verbose_name = "休暇種別"
        verbose_name_plural = "休暇種別"

    def __str__(self):
        return self.name


class Threshold(models.Model):
    role = models.CharField("職種", max_length=12, choices=ROLES, unique=True)
    count = models.PositiveSmallIntegerField(
        "注意する同時休暇人数", null=True, blank=True
    )

    class Meta:
        verbose_name = "職種別注意基準"
        verbose_name_plural = "職種別注意基準"

    def clean(self):
        if self.count is not None and self.count < 1:
            raise ValidationError("人数は1名以上、または未設定にしてください。")

    def __str__(self):
        return self.get_role_display()


class Leave(models.Model):
    KINDS = [("FULL", "全日"), ("AM", "午前休"), ("PM", "午後休"), ("TIME", "時間休暇")]
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, verbose_name="職員")
    date = models.DateField("日付")
    kind = models.CharField("休暇区分", max_length=4, choices=KINDS)
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, verbose_name="休暇種別"
    )
    start = models.TimeField("開始時刻", null=True, blank=True)
    end = models.TimeField("終了時刻", null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "休暇予定"
        verbose_name_plural = "休暇予定"
        ordering = ["date", "start", "staff__name"]

    def intervals(self):
        if self.kind == "FULL":
            return [(510, 750), (840, 1080)]
        if self.kind == "AM":
            return [(510, 750)]
        if self.kind == "PM":
            return [(840, 1080)]
        if not self.start or not self.end:
            return []
        a = self.start.hour * 60 + self.start.minute
        b = self.end.hour * 60 + self.end.minute
        return [
            (max(a, x), min(b, y))
            for x, y in [(510, 750), (840, 1080)]
            if max(a, x) < min(b, y)
        ]

    @property
    def minutes(self):
        return sum(b - a for a, b in self.intervals())

    def clean(self):
        super().clean()
        if self.kind == "TIME":
            if not self.start or not self.end:
                raise ValidationError("開始と終了時刻を入力してください。")
            if (
                self.start.second
                or self.end.second
                or self.start.microsecond
                or self.end.microsecond
            ):
                raise ValidationError("分単位で入力してください。")
            if not time(8, 30) <= self.start < self.end <= time(18):
                raise ValidationError(
                    "8:30〜18:00の範囲で、開始より後の終了時刻を指定してください。"
                )
            if not self.intervals():
                raise ValidationError("昼休憩だけの休暇は登録できません。")
        else:
            self.start = self.end = None
        if self.staff_id and self.date:
            for other in Leave.objects.filter(
                staff_id=self.staff_id, date=self.date
            ).exclude(pk=self.pk):
                if any(
                    a < d and c < b
                    for a, b in self.intervals()
                    for c, d in other.intervals()
                ):
                    raise ValidationError("本人の既存予定と時間が重複しています。")

    def __str__(self):
        return f"{self.date} {self.staff} {self.get_kind_display()}"
