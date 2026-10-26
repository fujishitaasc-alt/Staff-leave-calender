import calendar
from datetime import date
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, IntegrityError, OperationalError
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from .models import Leave, Staff, Threshold, ROLES
from .forms import LeaveForm
from .services import overlaps


@login_required
def calendar_view(request):
    today = timezone.localdate()
    try:
        first = (
            date.fromisoformat(
                request.GET.get("month", today.strftime("%Y-%m") + "-01") + "-01"
            )
            if len(request.GET.get("month", "")) == 7
            else today.replace(day=1)
        )
    except ValueError:
        first = today.replace(day=1)
    role = request.GET.get("role", "")
    if role not in dict(ROLES):
        role = ""
    records = Leave.objects.filter(
        date__year=first.year, date__month=first.month
    ).select_related("staff", "leave_type")
    if role:
        records = records.filter(staff__role=role)
    records = list(records)
    thresholds = dict(Threshold.objects.values_list("role", "count"))
    days = []
    for day in range(1, calendar.monthrange(first.year, first.month)[1] + 1):
        d = first.replace(day=day)
        rows = [r for r in records if r.date == d]
        groups = [
            {"name": name, "slots": overlaps(rows, key, thresholds.get(key))}
            for key, name in ROLES
            if not role or role == key
        ]
        days.append({"date": d, "rows": rows, "groups": groups})
    index = first.year * 12 + first.month - 1
    prev = date((index - 1) // 12, (index - 1) % 12 + 1, 1) if first.year > 1 else first
    nxt = (
        date((index + 1) // 12, (index + 1) % 12 + 1, 1) if first.year < 9999 else first
    )
    return render(
        request,
        "calendar.html",
        {
            "days": days,
            "first": first,
            "prev": prev,
            "next": nxt,
            "padding": range(first.weekday()),
            "roles": ROLES,
            "role": role,
        },
    )


@login_required
def mine(request):
    return render(
        request,
        "mine.html",
        {"rows": Leave.objects.filter(staff=request.user).select_related("leave_type")},
    )


@login_required
def edit(request, pk=None):
    item = get_object_or_404(Leave, pk=pk) if pk else Leave(staff=request.user)
    if item.staff_id != request.user.pk and not request.user.is_staff:
        return HttpResponseForbidden("権限がありません")
    form = LeaveForm(request.POST or None, instance=item)
    if request.method == "POST":
        saved = False
        try:
            with transaction.atomic():
                # Serialize writes for the same employee on PostgreSQL; SQLite serializes writes globally.
                Staff.objects.select_for_update().get(pk=item.staff_id)
                if form.is_valid():
                    form.save()
                    saved = True
        except (OperationalError, IntegrityError):
            saved = False
            form.add_error(None, "保存できませんでした。少し待って再度お試しください。")
        if saved:
            messages.success(request, "保存しました。予定は全員に共有されています。")
            return redirect("mine")
    return render(request, "form.html", {"form": form, "item": item})


@login_required
def cancel(request, pk):
    item = get_object_or_404(Leave, pk=pk)
    if item.staff_id != request.user.pk and not request.user.is_staff:
        return HttpResponseForbidden("権限がありません")
    if request.method == "POST":
        try:
            item.delete()
            messages.success(request, "予定を取り消しました。")
            return redirect("mine")
        except (OperationalError, IntegrityError):
            messages.error(request, "取消に失敗しました。再度お試しください。")
    return render(request, "cancel.html", {"item": item})
