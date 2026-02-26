"""Cached query helpers used by dialog entrypoints."""

from __future__ import annotations

import streamlit as st

from src.crud import (
    get_krs_needing_checkin,
    get_team_retrospectives,
    get_user_by_username,
    get_user_retrospectives,
    get_work_logs_by_date_range,
)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_user_by_username(username):
    return get_user_by_username(username)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_work_logs_by_range(user_id, start_date, end_date):
    return get_work_logs_by_date_range(user_id, start_date, end_date)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_user_retrospectives(user_id, cycle_id):
    return get_user_retrospectives(user_id, cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_team_retrospectives(manager_id, cycle_id):
    return get_team_retrospectives(manager_id, cycle_id)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get_krs_needing_checkin(user_id, cycle_id, days_threshold):
    return get_krs_needing_checkin(user_id, cycle_id, days_threshold)
