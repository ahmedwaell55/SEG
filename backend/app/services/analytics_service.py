from collections import Counter, defaultdict

from sqlalchemy.orm import Session, selectinload

from app.models import Client, Meeting


def dashboard_analytics(db: Session, user_id: int) -> dict:
    clients = db.query(Client).filter(Client.user_id == user_id).count()
    meetings = (
        db.query(Meeting)
        .join(Client, Meeting.client_id == Client.id)
        .options(selectinload(Meeting.client))
        .filter(Client.user_id == user_id)
        .all()
    )
    probabilities = [meeting.acceptance_probability for meeting in meetings if meeting.acceptance_probability is not None]
    sentiments = Counter(meeting.sentiment or "Unknown" for meeting in meetings)
    acceptance = Counter(meeting.acceptance_label or "Unknown" for meeting in meetings)

    monthly = defaultdict(lambda: {"meetings": 0, "avg_acceptance": 0, "_sum": 0})
    for meeting in meetings:
        key = meeting.meeting_date.strftime("%Y-%m")
        monthly[key]["meetings"] += 1
        if meeting.acceptance_probability is not None:
            monthly[key]["_sum"] += meeting.acceptance_probability

    trends = []
    for key in sorted(monthly.keys())[-6:]:
        item = monthly[key]
        trends.append(
            {
                "month": key,
                "meetings": item["meetings"],
                "avg_acceptance": round(item["_sum"] / item["meetings"], 1) if item["meetings"] else 0,
            }
        )

    top_sentiment = sentiments.most_common(1)[0][0] if sentiments else "No data"
    return {
        "total_clients": clients,
        "total_meetings": len(meetings),
        "high_acceptance_clients": acceptance.get("High", 0),
        "average_acceptance": round(sum(probabilities) / len(probabilities), 1) if probabilities else 0,
        "average_sentiment": top_sentiment,
        "sentiment_breakdown": dict(sentiments),
        "acceptance_breakdown": dict(acceptance),
        "conversion_trends": trends,
    }
