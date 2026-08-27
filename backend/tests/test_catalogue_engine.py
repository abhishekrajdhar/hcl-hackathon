"""Selection rules for discovered videos — pure, no DB and no network.

These encode the specific ways raw search results are bad, each of which was
observed in real output while building the catalogue rather than imagined.
"""

from __future__ import annotations

from app.catalogue.base import VideoRecord
from app.engines.catalogue.select import (
    MIN_RELEVANCE,
    Selection,
    relevance,
    score_candidate,
    select_videos,
    teaching_band,
)


def video(
    vid: str = "aaaaaaaaaaa",
    title: str = "Operating Systems Course for Beginners",
    channel: str = "freeCodeCamp.org",
    hours: float = 3.0,
    **kwargs,
) -> VideoRecord:
    return VideoRecord(
        video_id=vid, title=title, channel=channel, duration_hours=hours, **kwargs
    )


# --- relevance ---------------------------------------------------------------
def test_relevance_matches_whole_words_not_substrings() -> None:
    """"AI" must not match "snail". Substring matching put machine-learning
    content into a backend roadmap once already."""
    assert relevance("How to cook a snail", "AI", ("ai",)) == 0.0
    assert relevance("AI for Beginners", "AI", ("ai",)) == 1.0


def test_relevance_uses_aliases() -> None:
    """A skill's concrete handle carries the signal its formal name does not:
    nobody titles a video "Game Engines & Frameworks"."""
    title = "The Unity Tutorial For Complete Beginners"
    assert relevance(title, "Game Engines & Frameworks") < MIN_RELEVANCE
    assert relevance(title, "Game Engines & Frameworks", ("unity",)) == 1.0


def test_relevance_ignores_stopwords() -> None:
    assert relevance("Data Structures and Algorithms", "Data Structures & Algorithms") == 1.0


# --- hard rules --------------------------------------------------------------
def test_rejects_career_advice() -> None:
    """"Roadmap to Become an X" ranks high and teaches nothing."""
    assert score_candidate(video(title="Roadmap to Become a Prompt Engineer"), "Prompt Engineering") is None
    assert score_candidate(video(title="How much does a UI UX designer make?"), "User Interface Design") is None


def test_rejects_teasers_and_marathons() -> None:
    assert score_candidate(video(hours=0.02), "Operating Systems") is None, "40 seconds is not a lesson"
    assert score_candidate(video(hours=48.0), "Operating Systems") is None, "swamps any weekly budget"


def test_rejects_unavailable_video() -> None:
    assert score_candidate(video(is_available=False), "Operating Systems") is None


def test_rejects_off_topic_even_when_well_formed() -> None:
    assert score_candidate(video(title="Learn Python - Full Course"), "Computer Networks") is None


def test_unknown_language_is_not_a_rejection() -> None:
    """Most providers report no language. Rejecting on absence empties the
    catalogue; only a stated mismatch disqualifies."""
    assert score_candidate(video(language=None), "Operating Systems") is not None
    assert score_candidate(video(language="hi"), "Operating Systems") is None
    assert score_candidate(video(language="en-GB"), "Operating Systems") is not None


# --- selection ---------------------------------------------------------------
def test_one_pick_per_channel() -> None:
    """Search returns four parts of the same playlist. Offering "Part 1" and
    "Part 2" as a learner's two options is really offering one."""
    candidates = [
        video("aaaaaaaaaaa", "Operating Systems Course Part 1", "Gate Smashers", 1.0),
        video("bbbbbbbbbbb", "Operating Systems Course Part 2", "Gate Smashers", 1.0),
        video("ccccccccccc", "Operating Systems Course for Beginners", "freeCodeCamp.org", 4.0),
    ]
    picked = select_videos(candidates, "Operating Systems", limit=2)
    channels = [p.video.channel for p in picked]
    assert len(channels) == len(set(channels)), f"repeated channel in {channels}"
    assert set(channels) == {"Gate Smashers", "freeCodeCamp.org"}
    # Equal relevance, so the longer course leads on the duration tiebreak.
    assert picked[0].video.video_id == "ccccccccccc"


def test_excludes_ids_already_in_the_catalogue() -> None:
    candidates = [video("aaaaaaaaaaa"), video("bbbbbbbbbbb", channel="Neso Academy")]
    picked = select_videos(
        candidates, "Operating Systems", limit=2, exclude_ids=frozenset({"aaaaaaaaaaa"})
    )
    assert [p.video.video_id for p in picked] == ["bbbbbbbbbbb"]


def test_ordering_is_deterministic() -> None:
    """Same candidates in any order must yield the same picks, or a learner
    regenerating a roadmap gets a different plan for no reason."""
    candidates = [
        video("aaaaaaaaaaa", "Operating Systems Tutorial", "A", 1.0),
        video("bbbbbbbbbbb", "Operating Systems Tutorial", "B", 1.0),
        video("ccccccccccc", "Operating Systems Tutorial", "C", 1.0),
    ]
    first = [p.video.video_id for p in select_videos(candidates, "Operating Systems", limit=2)]
    second = [p.video.video_id for p in select_videos(list(reversed(candidates)), "Operating Systems", limit=2)]
    assert first == second


def test_type_follows_runtime() -> None:
    short = score_candidate(video(hours=0.3), "Operating Systems")
    long = score_candidate(video(hours=4.0), "Operating Systems")
    assert short is not None and short.resource_type == "video"
    assert long is not None and long.resource_type == "course"


def test_selection_carries_its_reasoning() -> None:
    picked = select_videos([video(hours=4.0)], "Operating Systems", limit=1)
    assert picked and picked[0].reasons, "a pick must be able to explain itself"


def test_teaching_band_matches_the_seed_table() -> None:
    """Discovered and seeded resources must describe coverage the same way."""
    assert teaching_band(1) == (0.0, 0.55)
    assert teaching_band(4) == (0.4, 0.85)
    assert teaching_band(99) == (0.0, 0.65), "unknown difficulty falls back, never raises"


def test_title_declared_language_is_a_stated_mismatch() -> None:
    """The scraper reports no language, so a title saying "in Hindi" is the
    only signal — and it must count. An unlabeled English title still passes."""
    from app.catalogue.base import VideoRecord
    from app.engines.catalogue.select import score_candidate

    hindi = VideoRecord(
        video_id="a" * 11,
        title="Prometheus Monitoring Full Tutorial in Hindi",
        channel="c",
        duration_hours=3.0,
    )
    assert score_candidate(hindi, "Monitoring", ("prometheus monitoring",)) is None

    english = VideoRecord(
        video_id="b" * 11,
        title="Prometheus Monitoring Full Tutorial",
        channel="c",
        duration_hours=3.0,
    )
    assert score_candidate(english, "Monitoring", ("prometheus monitoring",)) is not None
