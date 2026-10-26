def clock(n):
    return f"{n//60:02d}:{n%60:02d}"


def overlaps(leaves, role, threshold):
    rows = [r for r in leaves if r.staff.role == role]
    points = sorted({p for r in rows for interval in r.intervals() for p in interval})
    result = []
    for a, b in zip(points, points[1:]):
        people = {
            r.staff_id for r in rows if any(x < b and a < y for x, y in r.intervals())
        }
        if not people:
            continue
        count = len(people)
        if result and result[-1]["end"] == a and result[-1]["count"] == count:
            result[-1]["end"] = b
            result[-1]["label"] = clock(result[-1]["start"]) + "〜" + clock(b)
        else:
            result.append(
                {
                    "start": a,
                    "end": b,
                    "label": clock(a) + "〜" + clock(b),
                    "count": count,
                    "warn": threshold is not None and count >= threshold,
                }
            )
    return result
