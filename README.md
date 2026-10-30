# A/B Test 实验分析与决策工具

**A/B Testing Decision Toolkit** 是一个面向数据分析与商业分析场景的 Flask Web 项目。它把实验设计、实验质量检查、统计分析、护栏指标和业务判断组织成一套清晰、可复用的流程。

项目目标不是自动替代分析师做业务决策，而是：

> 把实验设计、实验质量检查、统计分析和业务判断组织成一个清晰、可复用的分析流程。
>
> link：https://ab-testing-decision-toolkit.onrender.com/

## 为什么做这个工具

只计算 p-value 容易忽略实验能否被正确解释。本项目希望展示一套更完整的分析思路：先设计实验和计划样本量，再检查 SRM 与数据质量，然后分析核心指标和护栏指标，最后结合置信区间与业务门槛形成谨慎结论。

## 完整分析流程

1. **实验设计**：定义 Baseline、最小可检测效应（MDE）、Alpha、Power、分流比例和实验周期。
2. **实验体检**：用样本比例异常检查（SRM）验证分流，并完成人工质量清单。
3. **指标分析**：根据指标类型自动选择两比例 Z 检验或韦尔奇 t 检验。
4. **护栏指标与多重检验**：同时分析一个核心指标和最多三个护栏指标，可选 Bonferroni 校正。
5. **实验决策总结**：区分统计显著性、期望方向、MDE、业务最低价值门槛和实验质量风险。

## 当前功能

- 比例型和均值型指标的实验前样本量规划
- 不等 A:B 分流比例
- 基于日流量的实验周期估算
- 卡方拟合优度检验进行 SRM 检查
- 八项实验质量 Checklist
- 单指标分析与多指标汇总
- 1 个核心指标 + 0～3 个护栏指标
- 不校正或 Bonferroni 多重检验控制
- 可选 Business Threshold
- A/B 核心指标对比图
- Observed Effect 与 95% CI 图
- 基于明确规则、非 AI 生成的决策总结

## 技术栈

- Python 3.11
- Flask / Jinja2
- statsmodels
- SciPy
- Gunicorn
- 原生 HTML、CSS、JavaScript
- pytest

项目不使用数据库，实验输入和计算结果不会被持久化保存。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

打开终端显示的地址，默认通常是：

```text
http://127.0.0.1:5000
```

如需继续使用作品集演示时的 5050 端口：

```bash
.venv/bin/gunicorn --bind 127.0.0.1:5050 app:app
```

访问：

```text
http://127.0.0.1:5050
```

本地地址依赖正在运行的 Python/Gunicorn 进程。关闭终端、结束会话或重启电脑后，需要重新执行启动命令。

## 运行测试

```bash
pytest -q
```

## 统计方法说明

### 两比例 Z 检验（Two-proportion Z-test）

用于比较两个独立实验组的比例型指标。比例 MDE 的用户输入单位为百分点（pp）：`0.67pp = 0.0067 decimal`。

### 韦尔奇独立样本 t 检验（Welch's t-test）

用于比较两个独立实验组的均值型指标，设置 `equal_var=False`，不要求两组方差相等。置信区间使用不等方差标准误和 Welch–Satterthwaite 自由度。

### 卡方拟合优度检验（Chi-square goodness-of-fit test）

用于 SRM 检查。其零假设是“实际样本分配符合预设分流比例”。SRM p-value 与指标效果检验的 p-value 对应不同的零假设，不能混用。

### 样本量规划

- 比例型指标使用 Cohen's h 和 `NormalIndPower`。
- 均值型指标使用实验前估计 SD、`effect_size = MDE / SD` 和 `TTestIndPower`。
- 均值型规划 SD 应优先来自历史数据、A/A Test 或类似实验，而不是使用已经结束实验的 Treatment SD 倒推设计。

### 多重检验

Bonferroni 校正使用 `Adjusted Alpha = Alpha / 正式检验数量`。它降低多重检验造成的假阳性风险，但也会让显著性判断更严格。

### MDE、Observed Effect 与 Business Threshold

- **MDE**：实验设计阶段希望有足够统计功效检测到的最小效果。
- **Observed Effect**：实验实际观察到的 B − A 差异。
- **Business Threshold**：业务认为值得进一步上线评估所需达到的最低效果。

Observed Effect 超过业务门槛，不代表一定应该上线；还需要检查置信区间、护栏指标和实验质量。

## 功能截图

项目完成公网部署后，可将首页、实验体检、指标汇总和决策总结截图放入 `docs/screenshots/`，用于简历或项目介绍。当前可直接启动本地应用进行现场演示。

## 公网部署

项目已包含：

- `Procfile`
- `render.yaml`
- `.python-version`
- Gunicorn 生产服务器依赖

Render 配置：

- Build Command：`pip install -r requirements.txt`
- Start Command：`gunicorn app:app`
- Health Check：`/`
- `SECRET_KEY`：由 Render 自动生成

部署需要先把项目放入 Git 仓库并连接 Render。免费 Web Service 长时间无请求后可能休眠，首次访问需要等待冷启动。

## 项目限制

- 只支持两个独立实验组 A/B。
- 不支持 CSV 上传、数据库、SQL、CUPED、Sequential Testing、ANOVA 或自动停止实验。
- 多重检验暂时只支持 Bonferroni。
- 汇总数据分析依赖输入的样本量、均值和标准差正确。
- 统计显著不等于业务上值得上线，也不代表结果没有偏差或实验设计一定正确。
- 免费托管适合作品集演示，不等同于高可用生产环境。

## 后续可扩展方向

- CSV 数据导入与字段映射
- 实验元数据和历史记录
- CUPED 方差缩减
- 留存等延迟成熟指标的观察窗口管理
- 更完整的实验报告导出
- 经充分设计后的序贯检验
