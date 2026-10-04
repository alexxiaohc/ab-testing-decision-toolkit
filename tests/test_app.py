import pytest

from app import (
    DEFAULT_FORM,
    analyze_ab_test,
    analyze_mean_test,
    analyze_metric_suite,
    app,
    check_srm,
    plan_proportion_experiment,
)


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def test_given_example_statistics_and_units():
    result = analyze_ab_test(
        users_a=27050,
        conversions_a=2164,
        users_b=26420,
        conversions_b=2299,
        mde_pp=0.67,
        alpha=0.05,
        power=0.8,
        direction="higher",
        metric_name="支付转化率",
    )

    assert result["rate_a"] == pytest.approx(0.08)
    assert result["rate_b"] == pytest.approx(0.0870174, abs=1e-7)
    assert result["difference"] == pytest.approx(0.0070174, abs=1e-7)
    # 内部的 0.007... 乘以 100 后，页面应展示为约 0.70 个百分点。
    assert result["difference"] * 100 == pytest.approx(0.70174, abs=1e-5)
    assert result["reaches_mde"] is True
    assert result["is_significant"] is True
    assert result["required_per_group"] == 26708
    assert result["sample_reached"] is False
    assert result["shortfall_b"] == 288


def test_refund_rate_uses_lower_is_better_direction():
    result = analyze_ab_test(
        users_a=2164,
        conversions_a=108,
        users_b=2299,
        conversions_b=161,
        mde_pp=0.67,
        alpha=0.05,
        power=0.8,
        direction="lower",
        metric_name="退款率",
    )

    assert result["rate_a"] == pytest.approx(0.0499076, abs=1e-7)
    assert result["rate_b"] == pytest.approx(0.0700304, abs=1e-7)
    assert result["difference"] == pytest.approx(0.0201229, abs=1e-7)
    assert result["relative_lift"] == pytest.approx(0.403203, abs=1e-6)
    assert result["p_value"] == pytest.approx(0.00475763, abs=1e-8)
    assert result["is_significant"] is True
    assert result["is_better"] is False
    assert result["change_word"] == "上升"
    assert result["reaches_mde"] is False
    assert result["required_per_group"] == 15504
    assert result["sample_reached"] is False


def test_page_renders_percentage_point_value(client):
    response = client.post(
        "/",
        data={
            "metric_type": "proportion",
            "metric_name": "支付转化率",
            "direction": "higher",
            "users_a": "27050",
            "conversions_a": "2164",
            "users_b": "26420",
            "conversions_b": "2299",
            "mde_pp": "0.67",
            "alpha": "0.05",
            "power": "0.8",
        },
    )

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "B 相比 A 提升" in page
    assert "0.70 个百分点" in page
    assert "比例差值 B − A = +0.0070" in page
    assert "当前样本量未达标" in page
    assert "B 组还差 288 人" in page


def test_refund_rate_page_marks_significant_increase_as_worse(client):
    response = client.post(
        "/",
        data={
            "metric_type": "proportion",
            "metric_name": "退款率",
            "direction": "lower",
            "users_a": "2164",
            "conversions_a": "108",
            "users_b": "2299",
            "conversions_b": "161",
            "mde_pp": "0.67",
            "alpha": "0.05",
            "power": "0.8",
        },
    )

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "退款率 · 越低越好" in page
    assert "B 组指标出现统计显著恶化" in page
    assert "B 相比 A 上升" in page
    assert "2.01 个百分点" in page
    assert "比例差值 B − A = +0.0201" in page
    assert "每组需要 15,504 人" in page


def test_invalid_conversion_count_shows_helpful_error(client):
    response = client.post(
        "/",
        data={
            "metric_type": "proportion",
            "metric_name": "退款率",
            "direction": "lower",
            "users_a": "100",
            "conversions_a": "101",
            "users_b": "100",
            "conversions_b": "10",
            "mde_pp": "1",
            "alpha": "0.05",
            "power": "0.8",
        },
    )

    assert "目标事件人数不能小于 0" in response.get_data(as_text=True)


def test_mean_metric_matches_expected_welch_results():
    result = analyze_mean_test(
        n_a=10000,
        mean_a=100,
        std_a=80,
        n_b=10000,
        mean_b=106,
        std_b=82,
        mde=5,
        alpha=0.05,
        power=0.8,
        direction="higher",
        metric_name="平均客单价",
    )

    assert result["difference"] == pytest.approx(6)
    assert result["relative_lift"] == pytest.approx(0.06)
    assert result["p_value"] == pytest.approx(1.6448e-7, rel=1e-4)
    assert result["ci_low"] == pytest.approx(3.7545, abs=1e-4)
    assert result["ci_high"] == pytest.approx(8.2455, abs=1e-4)
    assert result["is_significant"] is True
    assert result["is_better"] is True
    assert result["reaches_mde"] is True
    assert result["required_per_group"] == 4122
    assert result["sample_reached"] is True


def test_mean_metric_page_uses_welch_test(client):
    response = client.post(
        "/",
        data={
            "metric_type": "mean",
            "metric_name": "平均客单价",
            "direction": "higher",
            "mean_n_a": "10000",
            "mean_a": "100",
            "std_a": "80",
            "mean_n_b": "10000",
            "mean_b": "106",
            "std_b": "82",
            "mde_mean": "5",
            "alpha": "0.05",
            "power": "0.8",
        },
    )

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Welch&#39;s t-test" in page
    assert "+6.00" in page
    assert "1.645e-07" in page
    assert "[+3.75, +8.25]" in page
    assert "每组需要 4,122 人" in page
    assert "当前样本量已达标" in page


def test_mean_metric_validation_returns_clear_error(client):
    response = client.post(
        "/",
        data={
            "metric_type": "mean",
            "metric_name": "平均浏览时长",
            "direction": "higher",
            "mean_n_a": "1",
            "mean_a": "100",
            "std_a": "-1",
            "mean_n_b": "100",
            "mean_b": "101",
            "std_b": "10",
            "mde_mean": "1",
            "alpha": "0.05",
            "power": "0.8",
        },
    )

    assert "样本量都必须大于 1" in response.get_data(as_text=True)


def test_srm_case_detects_allocation_mismatch():
    result = check_srm(70420, 69580, 1, 1, 0.05)

    assert result["expected_a"] == pytest.approx(70000)
    assert result["expected_b"] == pytest.approx(70000)
    assert result["statistic"] == pytest.approx(5.04)
    assert result["p_value"] == pytest.approx(0.024768, abs=1e-6)
    assert result["has_srm"] is True


def test_proportion_design_keeps_percentage_point_units():
    result = plan_proportion_experiment(
        baseline_percent=8,
        mde_pp=0.8,
        alpha=0.05,
        power=0.8,
        ratio_a=1,
        ratio_b=1,
        direction="higher",
        daily_users=10000,
    )

    assert result["baseline"] == pytest.approx(0.08)
    assert result["mde"] == pytest.approx(0.008)
    assert result["target"] == pytest.approx(0.088)
    assert result["n_a"] == result["n_b"]
    assert result["days"] == pytest.approx((result["total"] + 9999) // 10000)


def test_guardrail_conflict_produces_cautious_summary():
    result = analyze_metric_suite(DEFAULT_FORM.copy())

    assert result["primary"]["outcome"] == "显著改善"
    assert result["guardrails"][0]["metric_name"] == "退款率"
    assert result["guardrails"][0]["outcome"] == "显著恶化"
    assert result["guardrails"][1]["outcome"] == "无显著变化"
    assert result["guardrail_risk"] is True
    assert result["status"] == "建议进一步验证"
    assert result["test_count"] == 3
    assert "直接全量上线" not in result["narrative"]


def test_business_threshold_uses_effect_and_full_confidence_interval():
    form = DEFAULT_FORM.copy()
    form.update(
        {
            "guardrail_count": "0",
            "primary_metric_type": "mean",
            "primary_metric_name": "每用户贡献利润",
            "primary_direction": "higher",
            "primary_n_a": "10000",
            "primary_mean_a": "100",
            "primary_std_a": "80",
            "primary_n_b": "10000",
            "primary_mean_b": "106",
            "primary_std_b": "82",
            "primary_mde_mean": "5",
            "business_threshold": "5",
        }
    )

    result = analyze_metric_suite(form)
    assert result["primary"]["effect_display"] == pytest.approx(6)
    assert result["observed_exceeds_threshold"] is True
    assert result["ci_exceeds_threshold"] is False


def test_suite_page_renders_bonferroni_and_decision_summary(client):
    form = DEFAULT_FORM.copy()
    form.update({"action": "suite", "active_step": "guardrails", "correction": "bonferroni"})
    response = client.post("/", data=form)
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Bonferroni 校正" in page
    assert "检验数量：" in page
    assert "0.0167" in page
    assert "退款率" in page
    assert "显著恶化" in page
    assert "建议进一步验证" in page
