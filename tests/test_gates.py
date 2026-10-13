import gates

REALS = ["UN calls US plans to livestream execution 'abhorrent'",
         "Moroccan king says migration cooperation model with Spain hit limit",
         "China and EU strike deal to halve Chinese hybrid exports"]
DAY = REALS + ["Trump strikes diesel deal with Putin", "Mexico court finds three men guilty"]


def test_good_fake_passes():
    assert gates.check_fake("Spain asks UN to fund umbrella museum in China", REALS, DAY) == []


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


def test_us_state_is_not_a_new_name():
    assert "new name" not in gates.check_fake("Trump to visit Iowa farms as China trade deal stalls", REALS, DAY + ["Trump visits farms"])
    assert "new name" not in gates.check_fake("Trump flies to New Mexico for China trade talks", REALS, DAY + ["Trump visits farms"])


def test_invented_person_still_fails_beside_a_state():
    assert "new name" in gates.check_fake("Trump meets Senator Hargreaves in Iowa over China deal", REALS, DAY)



def test_fake_that_extends_a_story_in_its_round_fails():
    reals = ["Rapid-fire with RHCP drummer Chad Smith: 'I'm known as Mocha Chad'",
             "UAE school pupils turn feathers into fertiliser as plans to combat waste take flight",
             "Japanese brewer designs 'wobbly' beer glass to encourage responsible drinking"]
    fake = "Chad Smith launches Mocha Chad coffee line, claims it fuels drum solos"
    assert "borrows from its round" in gates.check_fake(fake, reals, reals)


def test_one_shared_name_is_allowed():
    reals = ["Japanese brewer designs 'wobbly' beer glass to encourage responsible drinking",
             "UAE school pupils turn feathers into fertiliser as plans to combat waste take flight",
             "China unveils robot that helps farmers breed better wheat"]
    fake = "Japanese town pays residents to adopt abandoned vending machines"
    assert "borrows from its round" not in gates.check_fake(fake, reals, reals + ["town pays residents to adopt abandoned vending machines"])


def test_required_word_does_not_count_as_borrowing():
    reals = ["Trump says Nobel committee left a stain on Norway",
             "Trump picks Katie Zacharia as press secretary",
             "Trump slams Zelenskyy over diesel prices"]
    fake = "Trump orders gold-plated golf carts for Norway visit"
    assert "borrows from its round" not in gates.check_fake(fake, reals, reals, required="trump")



def test_fake_on_the_same_story_as_a_real_in_its_round_fails():
    # Charlie, 11/10/2026: "make sure they're not too similar like this".
    reals = ["Camels, goats, sheep: Ruto urges milk diversification as prices hit Sh85 a litre",
             "Japanese brewer designs 'wobbly' beer glass to encourage responsible drinking",
             "Candidate named Hitler Mussolini elected mayor in Peru"]
    fake = "Ruto proposes camel milk tax to curb rising dairy prices across Kenya"
    day = reals + ["Kenya dairy farmers face drought"]
    assert "same story" in gates.check_fake(fake, reals, day)


def test_fake_on_the_same_story_as_any_headline_today_fails():
    reals = ["Japanese brewer designs 'wobbly' beer glass to encourage responsible drinking",
             "Candidate named Hitler Mussolini elected mayor in Peru",
             "UAE school pupils turn feathers into fertiliser as plans to combat waste take flight"]
    day = reals + ["Kenya camel herders switch to selling milk as dairy prices soar"]
    fake = "Kenya taxes camel milk as dairy prices keep climbing"
    assert "same story" in gates.check_fake(fake, reals, day)


def test_a_different_story_with_one_shared_word_passes():
    reals = ["Japanese brewer designs 'wobbly' beer glass to encourage responsible drinking",
             "Candidate named Hitler Mussolini elected mayor in Peru",
             "UAE school pupils turn feathers into fertiliser as plans to combat waste take flight"]
    fake = "Peru town pays residents to adopt abandoned vending machines"
    assert "same story" not in gates.check_fake(fake, reals, reals)



def test_same_story_matches_word_forms():
    reals = ["Alberta woman, 61, breaks her own world record by planking for 5 hours",
             "UN calls US plans to livestream execution 'abhorrent'",
             "Candidate named Hitler Mussolini elected mayor in Peru"]
    fake = "Canadian health board bans plank competitions longer than three hours nationwide"
    assert "same story" in gates.check_fake(fake, reals, reals)



def test_a_fake_with_no_name_and_no_number_is_vague():
    day = ["Delaware farmers test new tractors this week", "Seoul council opens a robot cafe"]
    reals = ["Delaware farmers test new tractors this week"] * 3
    assert "vague" in gates.check_fake("Local farmers test robotic scarecrows across the state", reals, day)
    assert "vague" not in gates.check_fake("Delaware farmers test robotic scarecrows across fields", reals, day)
    assert "vague" not in gates.check_fake("Farmers test 40 robotic scarecrows across the state", reals, day)
