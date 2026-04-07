from pathlib import Path

from infrastructure.storage import UserConfigService


def test_user_config_service_round_trip_last_project_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config" / "user_config.json"
    service = UserConfigService(config_file=config_file)
    project_path = (tmp_path / "projects" / "my_project").resolve()

    service.save_last_project_path(project_path)

    assert service.load_last_project_path() == project_path
    assert config_file.exists()


def test_user_config_service_clears_last_project_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config" / "user_config.json"
    service = UserConfigService(config_file=config_file)
    project_path = (tmp_path / "projects" / "my_project").resolve()
    service.save_last_project_path(project_path)

    service.save_last_project_path(None)

    assert service.load_last_project_path() is None


def test_user_config_service_round_trip_projects_root_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config" / "user_config.json"
    service = UserConfigService(config_file=config_file)
    projects_root = (tmp_path / "projects_root").resolve()

    service.save_projects_root_path(projects_root)

    assert service.load_projects_root_path() == projects_root
    assert config_file.exists()


def test_user_config_service_clears_projects_root_path(tmp_path: Path) -> None:
    config_file = tmp_path / "config" / "user_config.json"
    service = UserConfigService(config_file=config_file)
    projects_root = (tmp_path / "projects_root").resolve()
    service.save_projects_root_path(projects_root)

    service.save_projects_root_path(None)

    assert service.load_projects_root_path() is None


def test_user_config_service_invalid_json_returns_no_last_project(tmp_path: Path) -> None:
    config_file = tmp_path / "config" / "user_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{not-json", encoding="utf-8")
    service = UserConfigService(config_file=config_file)

    assert service.load_last_project_path() is None
