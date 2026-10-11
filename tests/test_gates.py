import gates

REALS = ["UN calls US plans to livestream execution 'abhorrent'",
         "Moroccan king says migration cooperation model with Spain hit limit",
         "China and EU strike deal to halve Chinese hybrid exports"]
DAY = REALS + ["Trump strikes diesel deal with Putin", "Mexico court finds three men guilty"]


def test_good_fake_passes():
    assert gates.check_fake("Spain asks China to fund migration cooperation with EU", REALS, DAY) == []


def test_copy_of_a_real_fails():
    assert "overlap" in gates.check_fake("UN calls US plans to livestream an execution 'abhorrent'", REALS, DAY)


def test_length_fails_both_ways():
    assert "length" in gates.check_fake("Spain wins", REALS, DAY)
    long = " ".join(["China and EU agree"] * 6)
    assert "length" in gates.check_fake(long, REALS, DAY)


def test_allegation_fails():
    assert "allegation" in gates.check_fake("Putin arrested after diesel deal talks collapse in Spain", REALS, DAY)
    assert "allegation" in gates.check_fake("Trump diagnosed with dementia, aides say", REALS, DAY)


def test_new_proper_noun_fails():
    assert "new name" in gates.check_fake("Senator Jane Hargreaves backs China hybrid export deal", REALS, DAY)


def test_known_proper_noun_passes_case_insensitively():
    assert "new name" not in gates.check_fake("Putin offers Spain a diesel deal over migration", REALS, DAY)


def test_possessive_name_from_the_day_is_known():
    day = DAY + ["Trump picks Truth Social's Katie Zacharia as White House press secretary"]
    assert "new name" not in gates.check_fake("Truth Social's Katie Zacharia joins China trade talks", REALS, day)


import pytest


@pytest.mark.parametrize("fake", [
    "Trump suffers stroke at a rally in Spain, aides say",
    "Putin accused of stealing grain bound for Spain and China",
    "Trump undergoes surgery at a hospital in Spain",
    "Putin sued by China over Spain diesel deal",
    "Trump sentenced in Spain over China export deal",
    "Putin faces corruption probe in Spain",
    "Trump shot at in Spain during China talks",
    "Putin found guilty of smuggling diesel into Spain",
    "Trump collapses on stage in Spain, aides say",
    "Deaths in Spain blamed on China hybrid exports",
])
def test_allegation_gate_covers_health_and_crime(fake):
    assert "allegation" in gates.check_fake(fake, REALS, DAY)


def test_new_name_in_first_word_fails():
    assert "new name" in gates.check_fake("Hargreaves backs China hybrid export deal with Spain", REALS, DAY)
    assert "new name" in gates.check_fake("Musk says he will move his family to Spain next year", REALS, DAY)


def test_ordinary_first_word_known_from_the_day_passes():
    day = DAY + ["Officials say the plan is on hold"]
    assert "new name" not in gates.check_fake("Officials in Spain ask China to fund migration cooperation", REALS, day)


def test_required_word_gate():
    assert "required" in gates.check_fake("Putin offers Spain a diesel deal over migration", REALS, DAY, required="trump")
    assert "required" not in gates.check_fake("Trump offers Spain a diesel deal over migration", REALS, DAY, required="trump")


def test_fake_ending_in_a_bracket_fails():
    # Groq copied the source label from the prompt on 11/10/2026.
    assert "format" in gates.check_fake("Spain asks China to fund migration cooperation (Reuters)", REALS, DAY)
