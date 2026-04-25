"""MediaEditing Center — media editing & publishing."""
from sovereign.centers.simple_center import SimpleCenter

class MediaEditingCenter(SimpleCenter):
    CENTER_ID = 'media_editing_centre'
    DESCRIPTION = 'Media Editing & Publishing'
    PRIMARY_MODE = 'business'
    AGENTS = ['media_chief', 'content_production', 'publishing_queue', 'thumbnail_brief', 'clip_finder']
    DOMAIN_MAP = {'media': 'media_chief', 'publish': 'publishing_queue', 'thumbnail': 'thumbnail_brief', 'clip': 'clip_finder', 'content': 'content_production'}
    DEFAULT_AGENT = 'media_chief'

center = MediaEditingCenter()
