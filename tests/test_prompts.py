import json

import pytest

import prompts

POOL = [{"text": f"Headline number {i} about something odd", "source": "Reuters", "url": f"u{i}"} for i in range(40)]


def test_pick_prompt_numbers_every_headline():
    p = prompts.pick_prompt(POOL)
    assert "0. Headline number 0" in p and "39. Headline number 39" in p


def test_parse_pick_valid():
    raw = json.dumps({"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14]]})
    assert prompts.parse_pick(raw, 40)[4] == [12, 13, 14]


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
