from django import forms
from .models import Leave, LeaveType


class LeaveForm(forms.ModelForm):
    class Meta:
        model = Leave
        fields = ["date", "leave_type", "kind", "start", "end"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start": forms.TimeInput(
                attrs={"type": "time", "step": 60}, format="%H:%M"
            ),
            "end": forms.TimeInput(attrs={"type": "time", "step": 60}, format="%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["leave_type"].queryset = LeaveType.objects.filter(
            active=True
        ) | LeaveType.objects.filter(pk=self.instance.leave_type_id)
        self.fields["start"].help_text = (
            "時間休暇のみ入力。昼休憩 12:30〜14:00 は集計から除外します。"
        )
        if not self.instance.pk:
            default_type = self.fields["leave_type"].queryset.order_by("pk").first()
            if default_type:
                self.initial["leave_type"] = default_type.pk
