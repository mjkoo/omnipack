import pytest

from obtainium_pack.cli import main


def test_no_command_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert "required" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["verify", "report"])
def test_commands_are_registered_but_not_yet_implemented(command: str) -> None:
    with pytest.raises(NotImplementedError):
        main([command])
