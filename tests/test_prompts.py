import json

import pytest

import prompts

POOL = [{"text": f"Headline number {i} about something odd", "source": "Reuters", "url": f"u{i}"} for i in range(40)]


def test_pick_prompt_numbers_every_headline():
    p = prompts.pick_prompt(POOL)
    assert "0. Headline number 0" in p and "39. Headline number 39" in p


def test_parse_pick_valid():
    raw = json.dumps({"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14], [15, 16, 17]]})
    assert prompts.parse_pick(raw, 40)[5] == [15, 16, 17]


@pytest.mark.parametrize("rounds", [
    [[0, 1, 2]] * 5,                                                # duplicates across rounds
    [[0, 1, 99], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14]],  # out of range
    [[0, 1], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14]],      # short round
    [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]],                 # four rounds
])
def test_parse_pick_rejects_bad(rounds):
    with pytest.raises(ValueError):
        prompts.parse_pick(json.dumps({"rounds": rounds}), 40)


def test_fake_prompt_includes_notes_for_retries():
    rounds = [POOL[0:3], POOL[3:6]]
    p = prompts.fake_prompt(rounds, notes={1: ["length"]})
    assert "Round 2" in p and "length" in p


def test_parse_fakes():
    assert prompts.parse_fakes(json.dumps({"fakes": ["a b c d e", "f g h i j"]}), 2) == ["a b c d e", "f g h i j"]
    with pytest.raises(ValueError):
        prompts.parse_fakes(json.dumps({"fakes": ["only one"]}), 2)


def test_fake_prompt_lists_other_headlines_as_name_source():
    p = prompts.fake_prompt([POOL[0:3]], others=[POOL[20], POOL[21]])
    assert "Headline number 20" in p and "Headline number 21" in p
    assert "different event" in p


def test_pick_prompt_asks_for_different_stories_per_round():
    assert "three different stories" in prompts.pick_prompt(POOL)


def test_fake_prompt_states_required_word():
    assert "must mention Trump" in prompts.fake_prompt([POOL[0:3]], required="trump")
    assert "must mention" not in prompts.fake_prompt([POOL[0:3]])



def test_fake_prompt_does_not_show_source_labels():
    assert "(Reuters)" not in prompts.fake_prompt([POOL[0:3]])


def test_fake_prompt_steers_away_from_every_real_story():
    p = prompts.fake_prompt([POOL[0:3]], others=[POOL[20]])
    assert "never restate, paraphrase, extend or contradict" in p



def test_pick_prompt_states_the_mission_and_the_bar():
    p = prompts.pick_prompt(POOL)
    assert "how strange the world is" in p
    assert "Hitler Mussolini" in p          # the example he called really good
    assert "boring" in p


def test_trump_pick_prompt_asks_for_the_craziest():
    assert "craziest" in prompts.pick_prompt(POOL, required="trump")
    assert "Trump" in prompts.pick_prompt(POOL, required="trump")


def test_fake_prompt_gives_each_round_a_different_shape():
    p = prompts.fake_prompt([POOL[0:3], POOL[3:6], POOL[6:9]], seed="2026-10-11:normal")
    shapes = [line for line in p.splitlines() if line.startswith("Shape for this round:")]
    assert len(shapes) == 3 and len(set(shapes)) == 3


def test_fake_prompt_carries_the_good_fake_example():
    assert "misting poles" in prompts.fake_prompt([POOL[0:3]])



def test_no_shape_asks_for_a_short_headline():
    assert not any("nine words" in s for s in prompts.SHAPES)



def test_fake_prompt_gives_a_word_range_not_a_single_target():
    r = [{"text": "one two three four five six seven eight nine ten", "source": "X", "url": ""}] * 3
    p = prompts.fake_prompt([r])
    assert "Length: between 7 and 13 words." in p



def test_pick_prompt_and_parse_take_a_round_count():
    assert "Group them into 2 rounds" in prompts.pick_prompt(POOL, rounds=2)
    assert prompts.parse_pick(json.dumps({"rounds": [[0, 1, 2], [3, 4, 5]]}), 40, rounds=2) == [[0, 1, 2], [3, 4, 5]]


def test_fake_prompt_shows_the_spin_off_it_must_not_write():
    p = prompts.fake_prompt([POOL[0:3]])
    assert "plank competitions" in p and "different topic" in p


def test_no_invented_quote_from_a_named_person():
    p = prompts.fake_prompt([POOL[0:3]])
    assert "Never put invented words in a named person's mouth" in p
    assert any("unnamed" in s for s in prompts.SHAPES if "quote" in s)
