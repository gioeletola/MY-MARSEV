"""Diary Center — diary & reflection."""
from sovereign.centers.simple_center import SimpleCenter


class DiaryCenter(SimpleCenter):
    CENTER_ID = 'diary_centre'
    DESCRIPTION = 'Diary & Reflection'
    PRIMARY_MODE = 'personal'
    AGENTS = ['diary_chief', 'daily_reflection', 'mood_pattern', 'weekly_review', 'sunday_reset', 'impulse_filter']
    DOMAIN_MAP = {'diary': 'diary_chief', 'reflect': 'daily_reflection', 'mood': 'mood_pattern', 'weekly': 'weekly_review', 'sunday': 'sunday_reset', 'impulse': 'impulse_filter'}
    DEFAULT_AGENT = 'diary_chief'

center = DiaryCenter()
