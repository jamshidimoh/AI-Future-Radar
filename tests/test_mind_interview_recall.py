from src.protected_editorial_lane import SPECIAL_MAX_PER_PERIOD, is_mind_ideas_voices_candidate, mind_ideas_voices_score

def test_podcast_conversation_recall():
    item={"title":"Podcast: a conversation about AI consciousness","summary":"A deep discussion with a researcher","content_type":"video","source_type":"podcast","source":"Specialist Podcast","source_tier":1,"category":"mind"}
    before=mind_ideas_voices_score(item)
    assert is_mind_ideas_voices_candidate(item)
    assert mind_ideas_voices_score(item)==before

def test_mind_cap_unchanged():
    assert SPECIAL_MAX_PER_PERIOD==2
