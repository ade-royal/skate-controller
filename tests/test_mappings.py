import copy

from controller.mappings import DEFAULT_CONFIG, merge_update


def test_merge_update_ignores_unknown_and_invalid():
    config = copy.deepcopy(DEFAULT_CONFIG)
    merge_update(config, {"lean": {"source": "yaw", "invert": True}, "bogus": {"x": 1}})
    assert config["lean"] == {"source": "roll", "invert": True}
    assert "bogus" not in config


def test_merge_update_casts_numbers():
    config = copy.deepcopy(DEFAULT_CONFIG)
    merge_update(config, {"left_stick_x": {"deadzone_deg": 5}})
    assert config["left_stick_x"]["deadzone_deg"] == 5.0
