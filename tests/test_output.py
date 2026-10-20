from checkerboard_fmri_task.output import (
    default_output_dir,
    output_dir_problem,
    write_crash_report,
)


def test_default_output_dir_is_absolute():
    assert default_output_dir().is_absolute()


def test_writable_folder_is_created_and_left_clean(tmp_path):
    folder = tmp_path / "a" / "b"
    assert output_dir_problem(folder) is None
    assert folder.is_dir()
    assert list(folder.iterdir()) == []


def test_unwritable_folder_reports_why(tmp_path):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("")
    assert output_dir_problem(blocker / "data") is not None


def test_crash_report_falls_back_to_next_folder(tmp_path):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("")
    report = write_crash_report("boom", [blocker / "data", tmp_path / "fallback"])
    assert report is not None
    assert report.parent == tmp_path / "fallback"
    assert report.read_text(encoding="utf-8") == "boom"


def test_crash_report_returns_none_when_nowhere_works(tmp_path):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("")
    assert write_crash_report("boom", [blocker / "data"]) is None
