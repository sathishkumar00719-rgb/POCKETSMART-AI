"""
Simple in-memory storage for sessions and recommendation history.
Not persisted across restarts - swap for a real database in production.
"""
from datetime import datetime
from typing import Dict, List, Optional
from models import UserSession, RecommendationRecord

active_sessions: Dict[str, UserSession] = {}
user_recommendations: Dict[str, List[RecommendationRecord]] = {}


def save_to_history(username: str, recommendation_type: str, input_data: dict, result: dict) -> RecommendationRecord:
    summary_bits = []
    if recommendation_type == "home":
        summary_bits.append(f"Budget Rs.{input_data.get('total_budget', 0)}")
    elif recommendation_type == "party":
        summary_bits.append(f"{input_data.get('party_type', 'Party')} for {input_data.get('num_guests', '?')} guests")
    elif recommendation_type == "jewelry":
        summary_bits.append(f"{input_data.get('occasion', 'Occasion')} - Rs.{input_data.get('total_budget', 0)}")

    record = RecommendationRecord(
        username=username,
        recommendation_type=recommendation_type,
        input_summary=input_data,
        result_summary=", ".join(summary_bits) or "Recommendation generated",
        full_result=result,
    )
    user_recommendations.setdefault(username, []).append(record)
    return record


def get_history(username: str) -> List[RecommendationRecord]:
    return sorted(
        user_recommendations.get(username, []),
        key=lambda r: r.timestamp,
        reverse=True,
    )


def get_recommendation_by_id(username: str, recommendation_id: str) -> Optional[RecommendationRecord]:
    for item in user_recommendations.get(username, []):
        if item.id == recommendation_id:
            return item
    return None


def touch_session(username: str, token: str):
    now = datetime.utcnow()
    if username in active_sessions:
        active_sessions[username].last_activity = now
    else:
        active_sessions[username] = UserSession(
            username=username, login_time=now, last_activity=now, token=token, user_data={}
        )
