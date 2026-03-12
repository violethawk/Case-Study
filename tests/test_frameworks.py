from case_study.engine import load_frameworks


def test_load_frameworks_returns_list():
    frameworks = load_frameworks()
    assert isinstance(frameworks, list)
    assert len(frameworks) > 0


def test_each_framework_has_required_fields():
    frameworks = load_frameworks()
    for fw in frameworks:
        assert "name" in fw
        assert "full_name" in fw
        assert "description" in fw
        assert "best_for" in fw
        assert isinstance(fw["best_for"], list)
