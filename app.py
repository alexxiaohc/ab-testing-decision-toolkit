import math
import os

from flask import Flask, render_template, request, session
from scipy.stats import chisquare, t, ttest_ind_from_stats
from statsmodels.stats.power import NormalIndPower, TTestIndPower
from statsmodels.stats.proportion import (
    confint_proportions_2indep,
    proportion_effectsize,
    proportions_ztest,
)


app = Flask(__name__)
# 本地学习可直接运行；部署时应通过环境变量设置稳定且随机的 SECRET_KEY。
app.secret_key = os.environ.get("SECRET_KEY", "local-development-only-change-in-production")


QUALITY_CHECKS = [
    "已达到计划样本量",
    "未发现跨组污染",
    "未发现重复用户 / 重复记录异常",
    "实验曝光、支付、退款等埋点正常",
    "未发现严重的数据缺失",
    "已覆盖合理的业务周期",
    "指标观察窗口已经成熟",
    "未因中途看到 p < 0.05 而随意提前停止实验",
]


# 首页默认放入题目里的测试数据，打开页面就可以直接点击“开始分析”。
DEFAULT_FORM = {
    # 模块 1：实验设计
    "design_metric_type": "proportion",
    "design_metric_name": "支付转化率",
    "design_direction": "higher",
    "design_baseline_percent": "8",
    "design_mde_pp": "0.8",
    "design_baseline_mean": "100",
    "design_std": "80",
    "design_mde_mean": "5",
    "design_alpha": "0.05",
    "design_power": "0.8",
    "design_ratio_a": "1",
    "design_ratio_b": "1",
    "daily_users": "10000",
    # 模块 2：实验体检
    "srm_n_a": "70420",
    "srm_n_b": "69580",
    "srm_ratio_a": "1",
    "srm_ratio_b": "1",
    "srm_alpha": "0.05",
    # 模块 3：单指标分析（保留 V3 字段）
    "metric_type": "proportion",
    "metric_name": "支付转化率",
    "direction": "higher",
    "users_a": "27050",
    "conversions_a": "2164",
    "users_b": "26420",
    "conversions_b": "2299",
    "mde_pp": "0.67",
    "mean_n_a": "10000",
    "mean_a": "100",
    "std_a": "80",
    "mean_n_b": "10000",
    "mean_b": "106",
    "std_b": "82",
    "mde_mean": "5",
    "alpha": "0.05",
    "power": "0.8",
    # 模块 4/5：核心指标、护栏指标与决策总结
    "suite_alpha": "0.05",
    "suite_power": "0.8",
    "correction": "none",
    "guardrail_count": "2",
    "business_threshold": "",
    "primary_metric_type": "proportion",
    "primary_metric_name": "支付转化率",
    "primary_direction": "higher",
    "primary_users_a": "27050",
    "primary_events_a": "2164",
    "primary_users_b": "26420",
    "primary_events_b": "2299",
    "primary_mde_pp": "0.67",
    "primary_n_a": "10000",
    "primary_mean_a": "100",
    "primary_std_a": "80",
    "primary_n_b": "10000",
    "primary_mean_b": "106",
    "primary_std_b": "82",
    "primary_mde_mean": "5",
    "guardrail_1_metric_type": "proportion",
    "guardrail_1_metric_name": "退款率",
    "guardrail_1_direction": "lower",
    "guardrail_1_users_a": "2164",
    "guardrail_1_events_a": "108",
    "guardrail_1_users_b": "2299",
    "guardrail_1_events_b": "161",
    "guardrail_1_mde_pp": "0.67",
    "guardrail_1_n_a": "10000",
    "guardrail_1_mean_a": "10",
    "guardrail_1_std_a": "30",
    "guardrail_1_n_b": "10000",
    "guardrail_1_mean_b": "10.1",
    "guardrail_1_std_b": "31",
    "guardrail_1_mde_mean": "1",
    "guardrail_2_metric_type": "mean",
    "guardrail_2_metric_name": "每用户贡献利润",
    "guardrail_2_direction": "higher",
    "guardrail_2_users_a": "10000",
    "guardrail_2_events_a": "1000",
    "guardrail_2_users_b": "10000",
    "guardrail_2_events_b": "1050",
    "guardrail_2_mde_pp": "0.5",
    "guardrail_2_n_a": "10000",
    "guardrail_2_mean_a": "10",
    "guardrail_2_std_a": "30",
    "guardrail_2_n_b": "10000",
    "guardrail_2_mean_b": "10.1",
    "guardrail_2_std_b": "31",
    "guardrail_2_mde_mean": "1",
    "guardrail_3_metric_type": "proportion",
    "guardrail_3_metric_name": "自定义护栏指标",
    "guardrail_3_direction": "lower",
    "guardrail_3_users_a": "10000",
    "guardrail_3_events_a": "500",
    "guardrail_3_users_b": "10000",
    "guardrail_3_events_b": "480",
    "guardrail_3_mde_pp": "0.5",
    "guardrail_3_n_a": "10000",
    "guardrail_3_mean_a": "10",
    "guardrail_3_std_a": "3",
    "guardrail_3_n_b": "10000",
    "guardrail_3_mean_b": "9.8",
    "guardrail_3_std_b": "3.1",
    "guardrail_3_mde_mean": "0.5",
}


def analyze_ab_test(
    users_a: int,
    conversions_a: int,
    users_b: int,
    conversions_b: int,
    mde_pp: float,
    alpha: float,
    power: float,
    direction: str = "higher",
    metric_name: str = "支付转化率",
) -> dict:
    """计算 A/B Test 的核心指标，并返回适合页面展示的结果。"""
    if users_a <= 0 or users_b <= 0:
        raise ValueError("两组总样本数都必须大于 0。")
    if not 0 <= conversions_a <= users_a or not 0 <= conversions_b <= users_b:
        raise ValueError("目标事件人数不能小于 0，也不能超过对应组的总样本数。")
    if not 0 < mde_pp:
        raise ValueError("MDE 必须大于 0。")
    if not 0 < alpha < 1:
        raise ValueError("Alpha 必须在 0 和 1 之间。")
    if not 0 < power < 1:
        raise ValueError("Power 必须在 0 和 1 之间。")
    if direction not in {"higher", "lower"}:
        raise ValueError("请选择有效的指标期望方向。")
    metric_name = metric_name.strip()
    if not metric_name:
        raise ValueError("请填写指标名称。")

    rate_a = conversions_a / users_a
    rate_b = conversions_b / users_b
    difference = rate_b - rate_a

    # MDE 在页面上按“百分点”输入。例如 0.67 个百分点 = 0.0067 的转化率差值。
    mde = mde_pp / 100
    # 越高越好时，目标 B = Baseline + MDE；越低越好时则是 Baseline - MDE。
    direction_sign = 1 if direction == "higher" else -1
    target_rate_b = rate_a + direction_sign * mde
    if not 0 < target_rate_b < 1:
        raise ValueError("Baseline 按期望方向变化 MDE 后，目标比例必须在 0% 和 100% 之间。")

    # 双侧两比例 Z-test：原假设是 A、B 两组的真实转化率相同。
    z_statistic, p_value = proportions_ztest(
        count=[conversions_b, conversions_a],
        nobs=[users_b, users_a],
        alternative="two-sided",
    )

    # 95% 置信区间针对“B 转化率 - A 转化率”，使用容易理解的 Wald 方法。
    ci_low, ci_high = confint_proportions_2indep(
        count1=conversions_b,
        nobs1=users_b,
        count2=conversions_a,
        nobs2=users_a,
        method="wald",
        compare="diff",
        alpha=0.05,
    )

    # statsmodels 用 Cohen's h 表示两比例之间的效应量，再反推每组所需样本量。
    effect_size = abs(proportion_effectsize(target_rate_b, rate_a))
    required_per_group = math.ceil(
        NormalIndPower().solve_power(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            ratio=1,
            alternative="two-sided",
        )
    )

    relative_lift = difference / rate_a if rate_a > 0 else None
    # desired_change 始终用正数表示“朝期望方向改善”。
    desired_change = difference * direction_sign
    if difference > 0:
        change_word = "提升" if direction == "higher" else "上升"
    elif difference < 0:
        change_word = "下降"
    else:
        change_word = "无变化"

    return {
        "metric_type": "proportion",
        "metric_name": metric_name,
        "test_method": "Two-Proportion Z-Test",
        "direction": direction,
        "direction_label": "越高越好" if direction == "higher" else "越低越好",
        "rate_a": rate_a,
        "rate_b": rate_b,
        "difference": difference,
        "relative_lift": relative_lift,
        "p_value": float(p_value),
        "statistic": float(z_statistic),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "is_significant": bool(p_value < alpha),
        "is_better": desired_change > 0,
        "change_word": change_word,
        # “达到 MDE”按用户选择的期望方向判断，而不是固定认为 B > A 才是改善。
        "reaches_mde": desired_change >= mde,
        "required_per_group": required_per_group,
        "sample_reached": users_a >= required_per_group and users_b >= required_per_group,
        "shortfall_a": max(0, required_per_group - users_a),
        "shortfall_b": max(0, required_per_group - users_b),
        "mde": mde,
        "sample_note": "以 A 组比例为 Baseline，按期望方向设置目标 B 组比例，并假设两组人数相等。",
    }


def analyze_mean_test(
    n_a: int,
    mean_a: float,
    std_a: float,
    n_b: int,
    mean_b: float,
    std_b: float,
    mde: float,
    alpha: float,
    power: float,
    direction: str = "higher",
    metric_name: str = "平均客单价",
) -> dict:
    """使用汇总数据完成均值型指标的 Welch's t-test。"""
    if n_a <= 1 or n_b <= 1:
        raise ValueError("均值型指标的两组样本量都必须大于 1。")
    if std_a < 0 or std_b < 0:
        raise ValueError("标准差不能小于 0。")
    if std_a == 0 and std_b == 0:
        raise ValueError("两组标准差不能同时为 0，否则无法进行 Welch's t-test。")
    if mde <= 0:
        raise ValueError("MDE 必须大于 0。")
    if not 0 < alpha < 1:
        raise ValueError("Alpha 必须在 0 和 1 之间。")
    if not 0 < power < 1:
        raise ValueError("Power 必须在 0 和 1 之间。")
    if direction not in {"higher", "lower"}:
        raise ValueError("请选择有效的指标期望方向。")
    metric_name = metric_name.strip()
    if not metric_name:
        raise ValueError("请填写指标名称。")

    difference = mean_b - mean_a

    # Welch's t-test 在这里计算：equal_var=False 明确表示不假设两组方差相等。
    t_statistic, p_value = ttest_ind_from_stats(
        mean1=mean_b,
        std1=std_b,
        nobs1=n_b,
        mean2=mean_a,
        std2=std_a,
        nobs2=n_a,
        equal_var=False,
        alternative="two-sided",
    )

    # 95% CI 在这里计算：先求不等方差标准误，再用 Welch–Satterthwaite 自由度。
    variance_term_a = std_a**2 / n_a
    variance_term_b = std_b**2 / n_b
    standard_error = math.sqrt(variance_term_a + variance_term_b)
    degrees_of_freedom = (variance_term_a + variance_term_b) ** 2 / (
        variance_term_a**2 / (n_a - 1) + variance_term_b**2 / (n_b - 1)
    )
    critical_value = t.ppf(0.975, degrees_of_freedom)
    ci_low = difference - critical_value * standard_error
    ci_high = difference + critical_value * standard_error

    # 样本量在这里计算。规划时假设未来 A、B 等量，并用两组标准差的均方根
    # sqrt((std_a² + std_b²) / 2) 作为共同规划标准差。这保留了两组方差的信息，
    # 再用独立样本 t-test 的常用功效近似反推每组样本量。
    planning_std = math.sqrt((std_a**2 + std_b**2) / 2)
    effect_size = mde / planning_std
    required_per_group = math.ceil(
        TTestIndPower().solve_power(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            ratio=1,
            alternative="two-sided",
        )
    )

    relative_change = difference / mean_a if mean_a != 0 else None
    direction_sign = 1 if direction == "higher" else -1
    desired_change = difference * direction_sign
    if difference > 0:
        change_word = "提升" if direction == "higher" else "上升"
    elif difference < 0:
        change_word = "下降"
    else:
        change_word = "无变化"

    return {
        "metric_type": "mean",
        "metric_name": metric_name,
        "test_method": "Welch's t-test",
        "direction": direction,
        "direction_label": "越高越好" if direction == "higher" else "越低越好",
        "mean_a": mean_a,
        "mean_b": mean_b,
        "difference": difference,
        "relative_lift": relative_change,
        "p_value": float(p_value),
        "statistic": float(t_statistic),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "is_significant": bool(p_value < alpha),
        "is_better": desired_change > 0,
        "change_word": change_word,
        "reaches_mde": desired_change >= mde,
        "required_per_group": required_per_group,
        "sample_reached": n_a >= required_per_group and n_b >= required_per_group,
        "shortfall_a": max(0, required_per_group - n_a),
        "shortfall_b": max(0, required_per_group - n_b),
        "mde": mde,
        "planning_std": planning_std,
        "sample_note": (
            "假设未来两组等量；规划标准差采用当前两组标准差的均方根 "
            f"{planning_std:.2f}，样本量是独立样本 t-test 的功效近似。"
        ),
    }


def _validate_split(ratio_a: float, ratio_b: float) -> float:
    """校验 A:B 分流比例，并返回 statsmodels 使用的 B/A 样本量比。"""
    if ratio_a <= 0 or ratio_b <= 0:
        raise ValueError("A:B 分流比例的两个数都必须大于 0。")
    return ratio_b / ratio_a


def plan_proportion_experiment(
    baseline_percent: float,
    mde_pp: float,
    alpha: float,
    power: float,
    ratio_a: float,
    ratio_b: float,
    direction: str,
    daily_users: float | None = None,
) -> dict:
    """在实验开始前规划比例型指标的样本量。"""
    if not 0 < baseline_percent < 100:
        raise ValueError("比例型指标的 Baseline 必须在 0% 和 100% 之间。")
    if mde_pp <= 0:
        raise ValueError("最小可检测效应（MDE）必须大于 0。")
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("Alpha 和 Power 都必须在 0 和 1 之间。")
    if direction not in {"higher", "lower"}:
        raise ValueError("请选择有效的指标期望方向。")
    ratio = _validate_split(ratio_a, ratio_b)
    baseline = baseline_percent / 100
    mde = mde_pp / 100
    target = baseline + (mde if direction == "higher" else -mde)
    if not 0 < target < 1:
        raise ValueError("Baseline 按期望方向变化 MDE 后，目标比例必须在 0% 和 100% 之间。")

    effect_size = abs(proportion_effectsize(target, baseline))
    n_a = math.ceil(
        NormalIndPower().solve_power(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            ratio=ratio,
            alternative="two-sided",
        )
    )
    n_b = math.ceil(n_a * ratio)
    total = n_a + n_b
    days = None
    if daily_users is not None:
        if daily_users <= 0:
            raise ValueError("每日符合实验条件的总用户数必须大于 0。")
        days = math.ceil(total / daily_users)
    return {
        "metric_type": "proportion",
        "baseline": baseline,
        "target": target,
        "mde": mde,
        "mde_display": mde_pp,
        "alpha": alpha,
        "power": power,
        "ratio_a": ratio_a,
        "ratio_b": ratio_b,
        "n_a": n_a,
        "n_b": n_b,
        "total": total,
        "days": days,
    }


def plan_mean_experiment(
    baseline_mean: float,
    planning_std: float,
    mde: float,
    alpha: float,
    power: float,
    ratio_a: float,
    ratio_b: float,
    daily_users: float | None = None,
) -> dict:
    """使用实验前标准差估计规划均值型指标的样本量。"""
    if planning_std <= 0:
        raise ValueError("计划使用的标准差 SD 必须大于 0。")
    if mde <= 0:
        raise ValueError("最小可检测效应（MDE）必须大于 0。")
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("Alpha 和 Power 都必须在 0 和 1 之间。")
    ratio = _validate_split(ratio_a, ratio_b)
    effect_size = mde / planning_std
    n_a = math.ceil(
        TTestIndPower().solve_power(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            ratio=ratio,
            alternative="two-sided",
        )
    )
    n_b = math.ceil(n_a * ratio)
    total = n_a + n_b
    days = None
    if daily_users is not None:
        if daily_users <= 0:
            raise ValueError("每日符合实验条件的总用户数必须大于 0。")
        days = math.ceil(total / daily_users)
    return {
        "metric_type": "mean",
        "baseline_mean": baseline_mean,
        "planning_std": planning_std,
        "mde": mde,
        "alpha": alpha,
        "power": power,
        "ratio_a": ratio_a,
        "ratio_b": ratio_b,
        "n_a": n_a,
        "n_b": n_b,
        "total": total,
        "days": days,
    }


def check_srm(n_a: int, n_b: int, ratio_a: float, ratio_b: float, alpha: float) -> dict:
    """用卡方拟合优度检验检查样本比例异常（SRM）。"""
    if n_a <= 0 or n_b <= 0:
        raise ValueError("SRM 检查中的 A、B 实际样本量都必须大于 0。")
    if not 0 < alpha < 1:
        raise ValueError("SRM Alpha 必须在 0 和 1 之间。")
    _validate_split(ratio_a, ratio_b)
    total = n_a + n_b
    expected_a = total * ratio_a / (ratio_a + ratio_b)
    expected_b = total - expected_a
    statistic, p_value = chisquare(
        f_obs=[n_a, n_b],
        f_exp=[expected_a, expected_b],
    )
    has_srm = bool(p_value < alpha)
    return {
        "n_a": n_a,
        "n_b": n_b,
        "actual_a_share": n_a / total,
        "actual_b_share": n_b / total,
        "expected_a": expected_a,
        "expected_b": expected_b,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "alpha": alpha,
        "has_srm": has_srm,
        "message": (
            "检测到显著的样本比例异常（SRM）。建议先检查实验分流逻辑、埋点、数据缺失和过滤口径，再解释实验效果。"
            if has_srm
            else "暂未检测到显著的样本比例异常。"
        ),
    }


def _parse_metric_block(form, prefix: str, alpha: float, power: float) -> dict:
    """解析核心指标或某个护栏指标，并复用 V3 的两类统计函数。"""
    metric_type = form[f"{prefix}_metric_type"]
    common = {
        "metric_name": form[f"{prefix}_metric_name"],
        "direction": form[f"{prefix}_direction"],
        "alpha": alpha,
        "power": power,
    }
    if metric_type == "proportion":
        return analyze_ab_test(
            users_a=int(form[f"{prefix}_users_a"]),
            conversions_a=int(form[f"{prefix}_events_a"]),
            users_b=int(form[f"{prefix}_users_b"]),
            conversions_b=int(form[f"{prefix}_events_b"]),
            mde_pp=float(form[f"{prefix}_mde_pp"]),
            **common,
        )
    if metric_type == "mean":
        return analyze_mean_test(
            n_a=int(form[f"{prefix}_n_a"]),
            mean_a=float(form[f"{prefix}_mean_a"]),
            std_a=float(form[f"{prefix}_std_a"]),
            n_b=int(form[f"{prefix}_n_b"]),
            mean_b=float(form[f"{prefix}_mean_b"]),
            std_b=float(form[f"{prefix}_std_b"]),
            mde=float(form[f"{prefix}_mde_mean"]),
            **common,
        )
    raise ValueError("多指标分析中包含无效的指标类型。")


def _add_display_fields(result: dict) -> dict:
    """为汇总表和小型图表准备统一展示字段。"""
    if result["metric_type"] == "proportion":
        value_a = result["rate_a"] * 100
        value_b = result["rate_b"] * 100
        effect = result["difference"] * 100
        ci_low = result["ci_low"] * 100
        ci_high = result["ci_high"] * 100
        unit = "pp"
        value_unit = "%"
    else:
        value_a = result["mean_a"]
        value_b = result["mean_b"]
        effect = result["difference"]
        ci_low = result["ci_low"]
        ci_high = result["ci_high"]
        unit = ""
        value_unit = ""
    result.update(
        {
            "value_a": value_a,
            "value_b": value_b,
            "effect_display": effect,
            "ci_display_low": ci_low,
            "ci_display_high": ci_high,
            "effect_unit": unit,
            "value_unit": value_unit,
        }
    )
    return result


def analyze_metric_suite(form) -> dict:
    """分析一个核心指标和 0～3 个护栏指标，并应用可选 Bonferroni 校正。"""
    alpha = float(form["suite_alpha"])
    power = float(form["suite_power"])
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("多指标分析的 Alpha 和 Power 都必须在 0 和 1 之间。")
    guardrail_count = int(form["guardrail_count"])
    if not 0 <= guardrail_count <= 3:
        raise ValueError("护栏指标数量必须在 0 到 3 之间。")
    correction = form["correction"]
    if correction not in {"none", "bonferroni"}:
        raise ValueError("请选择有效的多重检验方法。")

    metrics = []
    primary = _add_display_fields(_parse_metric_block(form, "primary", alpha, power))
    primary["role"] = "核心指标"
    metrics.append(primary)
    for index in range(1, guardrail_count + 1):
        guardrail = _add_display_fields(
            _parse_metric_block(form, f"guardrail_{index}", alpha, power)
        )
        guardrail["role"] = f"护栏指标 {index}"
        metrics.append(guardrail)

    adjusted_alpha = alpha / len(metrics) if correction == "bonferroni" else alpha
    for metric in metrics:
        metric["raw_significant"] = bool(metric["p_value"] < alpha)
        metric["adjusted_significant"] = bool(metric["p_value"] < adjusted_alpha)
        significant_for_summary = metric["adjusted_significant"]
        if significant_for_summary and metric["is_better"]:
            metric["outcome"] = "显著改善"
        elif significant_for_summary and not metric["is_better"]:
            metric["outcome"] = "显著恶化"
        else:
            metric["outcome"] = "无显著变化"

    threshold_text = form.get("business_threshold", "").strip()
    business_threshold = None
    observed_exceeds = None
    ci_exceeds = None
    if threshold_text:
        business_threshold = float(threshold_text)
        if not math.isfinite(business_threshold) or business_threshold < 0:
            raise ValueError("业务最低价值门槛必须是大于或等于 0 的有效数字。")
        direction_sign = 1 if primary["direction"] == "higher" else -1
        desired_effect = primary["effect_display"] * direction_sign
        desired_ci_low = (
            primary["ci_display_low"]
            if direction_sign == 1
            else -primary["ci_display_high"]
        )
        observed_exceeds = desired_effect >= business_threshold
        ci_exceeds = desired_ci_low >= business_threshold

    max_value = max(abs(primary["value_a"]), abs(primary["value_b"]), 1e-12)
    primary["bar_a"] = max(2, abs(primary["value_a"]) / max_value * 100)
    primary["bar_b"] = max(2, abs(primary["value_b"]) / max_value * 100)
    threshold_raw = None
    if business_threshold is not None:
        threshold_raw = business_threshold * (1 if primary["direction"] == "higher" else -1)
    axis_values = [0, primary["ci_display_low"], primary["ci_display_high"], primary["effect_display"]]
    if threshold_raw is not None:
        axis_values.append(threshold_raw)
    axis_min = min(axis_values)
    axis_max = max(axis_values)
    padding = max((axis_max - axis_min) * 0.15, 0.01)
    axis_min -= padding
    axis_max += padding
    axis_span = axis_max - axis_min
    primary["ci_left"] = (primary["ci_display_low"] - axis_min) / axis_span * 100
    primary["ci_width"] = (primary["ci_display_high"] - primary["ci_display_low"]) / axis_span * 100
    primary["effect_position"] = (primary["effect_display"] - axis_min) / axis_span * 100
    primary["zero_position"] = (0 - axis_min) / axis_span * 100
    primary["threshold_position"] = (
        (threshold_raw - axis_min) / axis_span * 100 if threshold_raw is not None else None
    )

    guardrail_risk = any(
        metric["adjusted_significant"] and not metric["is_better"] for metric in metrics[1:]
    )
    primary_supported = primary["adjusted_significant"] and primary["is_better"]
    if not primary_supported:
        status = "核心指标未获得充分统计证据"
        narrative = "核心指标尚未获得充分统计证据，建议结合置信区间、样本量和业务背景继续评估。"
    elif guardrail_risk:
        status = "建议进一步验证"
        narrative = "核心指标改善，但存在护栏指标显著恶化风险，需要进一步验证或定位原因。"
    elif business_threshold is not None and not ci_exceeds:
        status = "建议进一步验证"
        narrative = "核心指标获得统计证据支持，但置信区间尚未完全超过业务门槛，建议结合风险与收益进一步评估。"
    else:
        status = "支持进一步上线评估"
        narrative = "核心指标获得统计证据支持，且当前未发现显著恶化的护栏指标；可进入进一步上线评估，但仍需结合实验质量和业务背景。"

    return {
        "metrics": metrics,
        "primary": primary,
        "guardrails": metrics[1:],
        "alpha": alpha,
        "test_count": len(metrics),
        "correction": correction,
        "correction_label": "Bonferroni 校正" if correction == "bonferroni" else "不校正",
        "adjusted_alpha": adjusted_alpha,
        "business_threshold": business_threshold,
        "observed_exceeds_threshold": observed_exceeds,
        "ci_exceeds_threshold": ci_exceeds,
        "guardrail_risk": guardrail_risk,
        "status": status,
        "narrative": narrative,
    }


def parse_form(form) -> dict:
    """把网页中的文字输入转换成统计计算需要的数字。"""
    try:
        metric_type = form["metric_type"]
        common_values = {
            "alpha": float(form["alpha"]),
            "power": float(form["power"]),
            "direction": form["direction"],
            "metric_name": form["metric_name"],
        }
        if metric_type == "proportion":
            values = {
                "metric_type": metric_type,
                "users_a": int(form["users_a"]),
                "conversions_a": int(form["conversions_a"]),
                "users_b": int(form["users_b"]),
                "conversions_b": int(form["conversions_b"]),
                "mde_pp": float(form["mde_pp"]),
                **common_values,
            }
        elif metric_type == "mean":
            values = {
                "metric_type": metric_type,
                "n_a": int(form["mean_n_a"]),
                "mean_a": float(form["mean_a"]),
                "std_a": float(form["std_a"]),
                "n_b": int(form["mean_n_b"]),
                "mean_b": float(form["mean_b"]),
                "std_b": float(form["std_b"]),
                "mde": float(form["mde_mean"]),
                **common_values,
            }
        else:
            raise ValueError("请选择有效的指标类型。")
    except (KeyError, TypeError, ValueError):
        raise ValueError("请在当前指标类型显示的所有输入框中填写有效数字。") from None

    number_values = [value for value in values.values() if isinstance(value, (int, float))]
    if not all(math.isfinite(value) for value in number_values):
        raise ValueError("输入不能是无穷大或非数字。")
    return values


@app.route("/", methods=["GET", "POST"])
def index():
    form_values = DEFAULT_FORM.copy()
    metric_result = None
    design_result = None
    suite_result = None
    errors = {}
    active_step = "overview"
    health_result = session.get("health_result")
    checked_quality = session.get("checked_quality", [])

    if request.method == "POST":
        form_values.update(request.form.to_dict())
        action = request.form.get("action", "metric_analysis")
        active_step = request.form.get("active_step", "analysis")
        try:
            if action == "design":
                design_type = request.form["design_metric_type"]
                daily_users = float(request.form["daily_users"])
                common = {
                    "alpha": float(request.form["design_alpha"]),
                    "power": float(request.form["design_power"]),
                    "ratio_a": float(request.form["design_ratio_a"]),
                    "ratio_b": float(request.form["design_ratio_b"]),
                    "daily_users": daily_users,
                }
                if design_type == "proportion":
                    design_result = plan_proportion_experiment(
                        baseline_percent=float(request.form["design_baseline_percent"]),
                        mde_pp=float(request.form["design_mde_pp"]),
                        direction=request.form["design_direction"],
                        **common,
                    )
                elif design_type == "mean":
                    design_result = plan_mean_experiment(
                        baseline_mean=float(request.form["design_baseline_mean"]),
                        planning_std=float(request.form["design_std"]),
                        mde=float(request.form["design_mde_mean"]),
                        **common,
                    )
                else:
                    raise ValueError("请选择有效的实验设计指标类型。")
            elif action == "health":
                health_result = check_srm(
                    n_a=int(request.form["srm_n_a"]),
                    n_b=int(request.form["srm_n_b"]),
                    ratio_a=float(request.form["srm_ratio_a"]),
                    ratio_b=float(request.form["srm_ratio_b"]),
                    alpha=float(request.form["srm_alpha"]),
                )
                checked_quality = sorted(set(request.form.getlist("quality_check")))
                health_result["quality_passed"] = len(checked_quality)
                health_result["quality_total"] = len(QUALITY_CHECKS)
                health_result["quality_risk"] = len(checked_quality) < len(QUALITY_CHECKS)
                session["health_result"] = health_result
                session["checked_quality"] = checked_quality
            elif action == "suite":
                suite_result = analyze_metric_suite(request.form)
                if health_result and (
                    health_result.get("has_srm") or health_result.get("quality_risk")
                ):
                    suite_result["status"] = "存在实验质量风险"
                    suite_result["narrative"] = (
                        "当前实验存在 SRM 或质量清单风险。建议先确认分流、埋点和数据完整性，再解释核心指标与护栏指标。"
                    )
            else:
                parsed_values = parse_form(request.form)
                metric_type = parsed_values.pop("metric_type")
                if metric_type == "proportion":
                    metric_result = analyze_ab_test(**parsed_values)
                else:
                    metric_result = analyze_mean_test(**parsed_values)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, ValueError) and str(exc):
                errors[action] = str(exc)
            else:
                errors[action] = "请检查当前模块的所有输入是否完整且格式正确。"

    return render_template(
        "index.html",
        form=form_values,
        result=metric_result,
        design_result=design_result,
        health_result=health_result,
        suite_result=suite_result,
        quality_checks=QUALITY_CHECKS,
        checked_quality=checked_quality,
        errors=errors,
        error=errors.get("metric_analysis"),
        active_step=active_step,
    )


if __name__ == "__main__":
    # debug=True 适合本地学习：修改代码后会自动重启，也会显示详细错误。
    app.run(debug=True)
