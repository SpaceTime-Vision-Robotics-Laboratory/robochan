from robochan import Action

def test_Action_ctor():
    action = Action("a", (5, 100))
    assert action.name == "a"
    assert action.parameters == (5, 100)

def test_Action_eq():
    action = Action("a", (5, 100))
    action2 = Action("a", (5, 100))
    action3 = Action("a", (100, ))

    assert action == action2
    assert action2 != action3
