# Patrol Planner 偏移几何数学原理

## 1. 坐标系统

### 局部平面投影

经纬度 $(\lambda, \phi)$ 投影到局部笛卡尔坐标 $(x, y)$：

$$
\begin{aligned}
x &= (\lambda - \lambda_0) \cdot R \cdot \cos\phi_0 \\
y &= (\phi - \phi_0) \cdot R
\end{aligned}
$$

其中：
- $R = 6{,}371{,}000\,\text{m}$ —— 地球半径
- $(\lambda_0, \phi_0)$ —— 投影参考点（多边形顶点均值）
- $x$ 轴指向东，$y$ 轴指向北

### 反投影

$$
\begin{aligned}
\lambda &= \lambda_0 + \frac{x}{R \cdot \cos\phi_0} \\
\phi &= \phi_0 + \frac{y}{R}
\end{aligned}
$$

---

## 2. 多边形偏移（Polygon Offset）

### 2.1 边偏移（Edge Offset）

给定一个顺时针多边形，将每条边沿其**内法线方向**平移距离 $d$。

对于边 $\overrightarrow{AB} = (B_x - A_x,\, B_y - A_y)$，单位内法线为：

$$
\hat{n} = \left( \frac{\Delta y}{L},\, -\frac{\Delta x}{L} \right), \quad
L = \sqrt{\Delta x^2 + \Delta y^2}
$$

平移后的边端点：

$$
A' = A + d \cdot \hat{n}, \quad B' = B + d \cdot \hat{n}
$$

### 2.2 顶点接合——Miter（尖角接合）

两条相邻平移边 $P_{i-1}'P_i'$ 和 $P_i'P_{i+1}'$ 的交点即为偏移后的顶点 $P_i^*$。

两直线求交：

$$
\begin{aligned}
P_i^* &= \frac{
\begin{vmatrix}
x_1 & y_1 \\ x_2 & y_2
\end{vmatrix}
(x_3 - x_4) -
\begin{vmatrix}
x_3 & y_3 \\ x_4 & y_4
\end{vmatrix}
(x_1 - x_2)
}{ (x_1 - x_2)(y_3 - y_4) - (y_1 - y_2)(x_3 - x_4) } \\[6pt]
&\text{（y 坐标同理）}
\end{aligned}
$$

若两条偏移线平行（退化情况），退化为两线段中点的均值。

---

## 3. Miter 放大效应（核心问题）

### 3.1 顶点内缩距离

在顶点 $V$ 处，内角为 $\theta$，边偏移量为 $d$，则偏移后顶点 $V^*$ 到原始顶点的距离为：

$$
\boxed{\|V^* - V\| = \frac{d}{\sin(\theta/2)}}
$$

**推导**：

两条边各平移 $d$ 后，偏移线交点 $V^*$ 位于原始角平分线上。从 $V$ 到 $V^*$ 的距离构成一个等腰三角形，底为 $d$，顶角为 $\theta$：

$$
\sin(\theta/2) = \frac{d}{\|V^* - V\|}
\quad\Rightarrow\quad
\|V^* - V\| = \frac{d}{\sin(\theta/2)}
$$

### 3.2 放大倍数

定义放大因子 $m$：

$$
m = \frac{1}{\sin(\theta/2)}
$$

| 内角 $\theta$ | $\sin(\theta/2)$ | 放大因子 $m$ | $d=1000$m 时顶点内缩 |
|---|---|---|---|
| $180^\circ$（平角） | $1.000$ | $1.00\times$ | $1000$ m |
| $150^\circ$ | $0.966$ | $1.04\times$ | $1035$ m |
| $120^\circ$ | $0.866$ | $1.15\times$ | $1155$ m |
| $90^\circ$ | $0.707$ | $1.41\times$ | $1414$ m |
| $60^\circ$ | $0.500$ | $2.00\times$ | $2000$ m |
| $40^\circ$ | $0.342$ | $2.92\times$ | $2927$ m |
| $20^\circ$ | $0.174$ | $5.76\times$ | $5760$ m |

**物理意义**：扫描传感器半径 $R$ 决定了最大可接受顶点内缩距离。要覆盖顶点，必须满足：

$$
\frac{d}{\sin(\theta/2)} \le R \quad\Rightarrow\quad d \le R \cdot \sin(\theta/2)
$$

最严格的约束来自**最尖锐的凸顶点**。

---

## 4. Chamfer Offset（切角偏移）解法

### 4.1 思路

保留直边段的偏移量 $d = R$（零浪费），但限制顶点处不超过 $R$：

$$
V^* = V + \min\left(1,\; \frac{R}{\|V_m - V\|}\right) \cdot (V_m - V)
$$

其中 $V_m$ 是 miter 交叉点。

等价于：沿角平分线将顶点拉回，使其到原始顶点的距离**不超过 $R$**。

### 4.2 实现

```python
# V     = 原始顶点
# V_m   = miter 交叉点
# R     = 最大允许偏移（= 扫描半径）

dist = |V_m - V|
if dist > R:
    scale = R / dist
    V_chamfer = V + scale * (V_m - V)
```

### 4.3 几何意义

| 位置 | 公式 | 覆盖情况 |
|---|---|---|
| 直边段 | $\|V^* - V\| = d = R$ | 扫描圈外缘**刚好触及**边界 |
| 顶点 | $\|V^* - V\| = R$ （钳位后） | 扫描圈外缘**刚好触及**顶点 |

### 4.4 为什么只对第一圈做切角

切角操作会改变多边形拓扑——尖锐的角被"切掉"后，该处的内角接近 $180^\circ$（平角）。后续圈从这个已修形的多边形继续偏移时：

$$
m = \frac{1}{\sin(180^\circ/2)} = \frac{1}{\sin 90^\circ} = 1.00
$$

放大因子接近 $1$，不再产生深度畸变。如果对每一圈都做切角，切角产生的新边会在后续偏移中持续繁殖，导致顶点数雪崩。

---

## 5. 回字间距设计

### 5.1 层间距

相邻回字之间的间距等于传感器直径：

$$
\text{spacing} = 2 \times R
$$

这样相邻回字的扫描覆盖圈在中间刚好相接：

```
         ← R →│← R →
    ─────●────┼─────●─────    （上层路径）
               ↑ 相接点
    ─────●────┼─────●─────    （下层路径）
```

### 5.2 首圈内缩

首圈内缩量 $d = R$（配合切角），使得：

- **直边处**：扫描圈外缘触及多边形边界，零浪费
- **顶点处**：扫描圈外缘触及原始顶点，零遗漏

### 5.3 覆盖完整性

对于宽度 $W$ 的区域，需要的回字层数：

$$
n = \left\lceil \frac{W - 2R}{2R} \right\rceil + 1
$$

其中第一层覆盖 $[0, 2R]$ 区间（从边界向内），后续每层覆盖 $[2kR,\, 2(k+1)R]$。

---

## 6. 去重（Deduplication）

路径加密后，相邻航点间距离可能小于 $\epsilon$（浮点精度或闭合段导致）。去重函数：

```python
# 仅保留与前一点距离 > ε 的点
cleaned = []
for p in points:
    if not cleaned or |p - cleaned[-1]| > ε:
        cleaned.append(p)
```

默认 $\epsilon = 10^{-6}\,\text{m}$（1 微米），消除：

1. **双重闭合重复**：`loop + [loop[0]]` 后再 `densify + [densified[0]]` 导致的末端重叠
2. **加密插值重合**：在极短边上加密时，插值点落在已有点上
