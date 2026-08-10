from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user

from app.core.database import get_db
from app.models.history import AnalysisHistory
from app.schemas.analyze import StatsResponse, EventMetadata

router = APIRouter()


@router.get("/", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    from datetime import datetime, timedelta
    from collections import Counter

    records = db.query(AnalysisHistory).all()
    total = len(records)
    critical = 0
    total_time = 0.0

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_errors = Counter()
    
    # Initialize daily trends for the last 7 days (including today)
    daily_trends = { (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(6, -1, -1) }
    type_distribution = Counter()

    for record in records:
        total_time += record.search_time_ms or 0
        if record.event_metadata:
            meta = EventMetadata(**record.event_metadata)
            if meta.isCritical:
                critical += 1
            if meta.provider:
                type_distribution[meta.provider] += 1
            
        if record.created_at and record.created_at >= one_week_ago:
            if record.event_id and record.event_id != "Unknown":
                weekly_errors[(record.event_id, record.provider)] += 1
                
        if record.created_at:
            day_str = record.created_at.strftime('%Y-%m-%d')
            if day_str in daily_trends:
                daily_trends[day_str] += 1

    top_weekly_error = None
    if weekly_errors:
        (top_event_id, top_provider), count = weekly_errors.most_common(1)[0]
        top_weekly_error = {
            "eventId": top_event_id,
            "provider": top_provider,
            "count": count
        }

    avg_sec = round(total_time / total / 1000, 2) if total else 0.0
    
    daily_trends_list = [{"date": k, "count": v} for k, v in daily_trends.items()]
    type_dist_list = [{"name": k, "value": v} for k, v in type_distribution.most_common(5)]
    
    # Group others if there are more than 5
    if len(type_distribution) > 5:
        other_count = sum(v for k, v in type_distribution.most_common()[5:])
        type_dist_list.append({"name": "Other", "value": other_count})

    return StatsResponse(
        totalLogs=total,
        criticalErrors=critical,
        avgSearchTimeSec=avg_sec,
        topWeeklyError=top_weekly_error,
        dailyTrends=daily_trends_list,
        typeDistribution=type_dist_list
    )


@router.get("/correlations")
def get_correlations(
    db: Session = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """Find correlated event IDs: events that frequently co-occur or repeat in patterns."""
    from datetime import datetime, timedelta
    from collections import Counter, defaultdict

    records = db.query(AnalysisHistory).order_by(AnalysisHistory.created_at).all()

    # --- 1. Frequency: top repeated event IDs ---
    freq_counter = Counter()
    for r in records:
        if r.event_id and r.event_id != "Unknown":
            freq_counter[(r.event_id, r.provider or "Unknown")] += 1

    top_repeated = [
        {
            "eventId": eid,
            "provider": prov,
            "count": cnt,
            "type": "repeated",
            "label": f"Event {eid} recurred {cnt}x"
        }
        for (eid, prov), cnt in freq_counter.most_common(5)
        if cnt >= 2
    ]

    # --- 2. Time correlation: events within 5-minute windows ---
    time_pairs = Counter()
    window_minutes = 5
    for i, a in enumerate(records):
        if not a.created_at or not a.event_id or a.event_id == "Unknown":
            continue
        for b in records[i+1:]:
            if not b.created_at:
                break
            diff = abs((b.created_at - a.created_at).total_seconds())
            if diff > window_minutes * 60:
                break
            if b.event_id and b.event_id != a.event_id and b.event_id != "Unknown":
                pair = tuple(sorted([a.event_id, b.event_id]))
                time_pairs[pair] += 1

    time_correlated = [
        {
            "eventIds": list(pair),
            "count": cnt,
            "type": "time_correlated",
            "label": f"Event {pair[0]} & {pair[1]} occurred within 5 min ({cnt}x)"
        }
        for pair, cnt in time_pairs.most_common(5)
        if cnt >= 2
    ]

    # --- 3. Critical event clusters (same day) ---
    daily_critical = defaultdict(list)
    for r in records:
        if r.created_at and r.event_metadata:
            meta = EventMetadata(**r.event_metadata)
            if meta.isCritical and r.event_id != "Unknown":
                day = r.created_at.strftime("%Y-%m-%d")
                daily_critical[day].append(r.event_id)

    critical_clusters = []
    for day, events in daily_critical.items():
        if len(events) >= 2:
            unique_events = list(set(events))
            critical_clusters.append({
                "date": day,
                "eventIds": unique_events[:5],
                "count": len(events),
                "type": "critical_cluster",
                "label": f"{len(events)} critical events on {day}: {', '.join(unique_events[:3])}"
            })
    critical_clusters.sort(key=lambda x: x["date"], reverse=True)
    critical_clusters = critical_clusters[:5]

    return {
        "topRepeated": top_repeated,
        "timeCorrelated": time_correlated,
        "criticalClusters": critical_clusters,
        "hasInsights": bool(top_repeated or time_correlated or critical_clusters)
    }
