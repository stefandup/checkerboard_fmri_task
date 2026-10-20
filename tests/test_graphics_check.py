from checkerboard_fmri_task.graphics_check import graphics_problem, opengl_problem


def test_real_driver_has_no_problem():
    assert graphics_problem(["Intel(R) UHD Graphics 620"], remote_session=False) is None


def test_basic_display_adapter_is_reported():
    problem = graphics_problem(["Microsoft Basic Display Adapter"], remote_session=False)
    assert problem is not None
    assert "No graphics driver" in problem


def test_real_driver_alongside_fallback_is_fine():
    adapters = ["Microsoft Basic Display Adapter", "NVIDIA GeForce RTX 3060"]
    assert graphics_problem(adapters, remote_session=False) is None


def test_remote_desktop_is_reported():
    problem = graphics_problem(["NVIDIA GeForce RTX 3060"], remote_session=True)
    assert problem is not None
    assert "Remote Desktop" in problem


def test_unknown_adapters_are_not_reported():
    # Off Windows, or if the lookup finds nothing: don't guess.
    assert graphics_problem([], remote_session=False) is None


def test_opengl_3_3_is_enough():
    assert opengl_problem((3, 3)) is None
    assert opengl_problem((4, 6)) is None


def test_old_opengl_is_reported():
    # Intel HD Graphics 3000 tops out at 3.1; Windows' own fallback gives 1.1.
    for version in [(3, 1), (1, 1)]:
        problem = opengl_problem(version)
        assert problem is not None
        assert "needs 3.3" in problem
