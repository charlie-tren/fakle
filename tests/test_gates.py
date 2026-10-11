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
