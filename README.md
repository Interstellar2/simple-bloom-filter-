# 布隆过滤器：用"打卡墙"判断你来过没

[![Python Versions](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English README](./README_EN.md)

## 安装

```bash
git clone https://github.com/yourname/simple-bloom-filter.git
cd simple-bloom-filter
pip install -e .
```

运行 embedding 缓存 demo 需要额外安装 Redis 依赖：

```bash
pip install -e ".[redis]"
```

## 一句话总结

布隆过滤器就像一个**超级省空间的签到表**，专门回答一个问题：

> **"这个网址，我以前有没有访问过？"**

它的答案只有两种：

- **"一定没访问过"** → 真的没访问过，错不了。
- **"可能访问过"** → 大概率访问过，但也有小概率搞错（误判）。

所以它的特点是：**宁可说错"访问过"，也绝不会漏掉"没访问过"**。

---

## 一、用一个生活例子理解它

想象学校门口有一面**打卡墙**，墙上有一排灯，一开始全是灭的。

```text
打卡墙（一开始所有灯都关着）

位置:  0   1   2   3   4   5   6   7   8   9   10  11  ...
      ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬────┐
灯:   │ ░ │ ░ │ ░ │ ░ │ ░ │ ░ │ ░ │ ░ │ ░ │ ░ │ ░ │ ░ │... │
      └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴────┘
           ░ = 灯灭了（表示 0）
```

每个学生进校门时，都要用 3 个不同的印章，在墙上按下 3 个位置。印章是按名字算出来的：同一个名字，永远按同样的 3 个位置。

比如小明来了，他的 3 个印章按在位置 `1`、`4`、`8`：

```text
小明打卡后

位置:  0   1   2   3   4   5   6   7   8   9   10  11  ...
      ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬────┐
灯:   │ ░ │ ▓ │ ░ │ ░ │ ▓ │ ░ │ ░ │ ░ │ ▓ │ ░ │ ░ │ ░ │... │
      └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴────┘
              明1      明2              明3
           ▓ = 灯亮了（表示 1）
```

---

## 二、怎么判断某个人来过没？

老师想知道"小明今天来过学校吗？"，就把小明的名字再算一遍 3 个印章位置，然后去墙上检查：

- 如果这 3 个位置的灯**全都亮着** → **"可能来过"** ✅
- 如果其中**有任何一个灯是灭的** → **"一定没来过"** ❌

```text
检查小明

位置:  0   1   2   3   4   5   6   7   8   9   10  11  ...
      ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬────┐
灯:   │ ░ │ ▓ │ ░ │ ░ │ ▓ │ ░ │ ░ │ ░ │ ▓ │ ░ │ ░ │ ░ │... │
      └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴────┘
              ✓       ✓               ✓

三个位置全亮 → 小明可能来过
```

---

## 三、为什么会误判？

再来看一个例子。

小红来了，她的印章按在位置 `1`、`4`、`10`：

```text
小红打卡后

位置:  0   1   2   3   4   5   6   7   8   9   10  11  ...
      ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬────┐
灯:   │ ░ │ ▓ │ ░ │ ░ │ ▓ │ ░ │ ░ │ ░ │ ▓ │ ░ │ ▓ │ ░ │... │
      └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴────┘
              明/红   明1     明2             红3
```

注意位置 `1` 和 `4` 小明和小红都按过了，但灯只亮一次就够了。

现在来了一个**从没来过**的小刚，他的印章位置恰好也是 `1`、`4`、`10`。

```text
检查小刚（其实他没来过）

位置:  0   1   2   3   4   5   6   7   8   9   10  11  ...
      ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬────┐
灯:   │ ░ │ ▓ │ ░ │ ░ │ ▓ │ ░ │ ░ │ ░ │ ▓ │ ░ │ ▓ │ ░ │... │
      └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴────┘
              ✓       ✓               ✓ ← 这三个亮灯其实是别人留下的！

小刚的三个位置全亮 → 误判：小刚"可能来过"
```

这就是布隆过滤器的**误判**：小刚明明没来过，但因为他的印章位置碰巧被小明和小红"占过坑"，系统以为他也来过。

---

## 四、怎么减少误判？

误判就像撞衫，撞的人越多越容易撞。减少误判有几个办法：

| 方法 | 解释 |
|------|------|
| **把墙变大** | 灯越多，每个人占的位置越分散，撞到别人的概率越小 |
| **多按几个印章** | 每个人按 3 个改成按 7 个，要全撞上的难度就变大了 |
| **少记录一些人** | 墙上人太多，灯大部分都亮了，自然容易误判 |

但天下没有免费的午餐：

- 墙越大，占地方越多。
- 印章越多，计算越慢。

所以实际使用时要**提前想好**：大概要记多少个网址？能接受多高的误判率？然后自动算出最合适的墙大小和印章数量。

---

## 五、回到网址过滤的场景

现在把"学生打卡"换成"网址访问"：

| 生活例子 | 程序里的对应 |
|----------|--------------|
| 打卡墙 | 一个很长的二进制位数组（全是 0 和 1） |
| 灯亮了 | 对应位置变成 1 |
| 灯灭了 | 对应位置还是 0 |
| 印章 | 哈希函数，把网址变成位置编号 |
| 学生名字 | 网址 URL |

每次访问一个网址，就用几个哈希函数算出几个位置，把位置都标成 1。

每次查一个网址，也用同样的哈希函数算位置：

- 全是 1 → 可能访问过
- 有 0 → 一定没访问过

---

## 六、它的优缺点

### 优点

- **特别省内存**：存一个网址不需要把整串字符都记下来，只需要几个 bit。
- **查询特别快**：算几个哈希值，查几个位，一下子就出结果。
- **绝不会漏判**：没访问过的网址不会被说成"一定访问过"。

### 缺点

- **可能误判**：会把没访问过的网址判断成"可能访问过"。
- **不能删记录**：如果把某个位置清 0，可能会把别人的记录也擦掉。
- **只能回答"在不在"**：不能告诉你具体访问了哪些网址。

---

## 七、用在哪些地方？

| 场景 | 为什么用布隆过滤器 |
|------|-------------------|
| **浏览器/爬虫去重** | 判断这个网页有没有抓取过 |
| **缓存防击穿** | 先问布隆过滤器"数据库里有没有"，没有就直接拒绝，避免打到数据库 |
| **垃圾邮件黑名单** | 快速判断一个邮箱/网址是否在黑名单 |
| **推荐系统** | 判断用户有没有看过这个视频/文章 |

---

## 八、Python 代码示例

```python
import hashlib
import math


class BloomFilter:
    def __init__(self, expected_items: int, false_positive_rate: float):
        """
        expected_items: 预计要存的网址数量
        false_positive_rate: 能接受的误判率，比如 0.01 表示 1%
        """
        self.size = math.ceil(
            -(expected_items * math.log(false_positive_rate)) / (math.log(2) ** 2)
        )
        self.hash_count = math.ceil((self.size / expected_items) * math.log(2))
        self.bit_array = bytearray(self.size)

    def _hashes(self, item: str):
        """用一个网址算出 k 个位置"""
        item_bytes = item.encode("utf-8")
        h1 = int(hashlib.md5(item_bytes).hexdigest(), 16)
        h2 = int(hashlib.sha1(item_bytes).hexdigest(), 16)

        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item: str):
        """记录一个网址访问过"""
        for pos in self._hashes(item):
            self.bit_array[pos] = 1

    def __contains__(self, item: str) -> bool:
        """判断一个网址是否可能访问过"""
        return all(self.bit_array[pos] == 1 for pos in self._hashes(item))


# 使用
bf = BloomFilter(expected_items=10000, false_positive_rate=0.01)

bf.add("https://www.google.com")
bf.add("https://www.github.com")

print("https://www.google.com" in bf)    # True  （可能访问过）
print("https://www.fake-site.com" in bf) # False （一定没访问过）
```

完整可运行代码见：[demos/basic_demo.py](./demos/basic_demo.py)

---

## 九、进阶案例：用布隆过滤器给 Embedding 缓存加速

除了判断网址有没有访问过，布隆过滤器还很适合做**缓存前的快速过滤层**。

### 场景：Embedding 服务缓存

假设你有一个 AI 服务，输入一段文本，输出一个 embedding 向量。计算 embedding 很慢、很贵，所以我们想把结果缓存到 Redis 里。

但如果每次请求都先查 Redis，很多请求其实根本没缓存过，白查一次。

这时候可以在 Redis 前面加一层布隆过滤器：

```text
输入文本
   ↓
布隆过滤器（第一层）
   ↓ 一定没缓存过
直接调模型计算 embedding → 写入 Redis → 返回
   ↓ 可能缓存过
Redis（第二层）
   ↓ 命中
直接返回缓存的 embedding
   ↓ 没命中（布隆过滤器误判）
调模型计算 → 写入 Redis → 返回
```

### 为什么这样设计？

| 层级 | 作用 | 特点 |
|------|------|------|
| **布隆过滤器** | 快速判断"是否可能缓存过" | 内存极小、速度极快，但可能误判 |
| **Redis** | 精确存储真正的 embedding | 容量大、精确，但查询比布隆过滤器慢 |

布隆过滤器帮 Redis 挡掉大量"肯定没缓存"的请求，只有它说"可能缓存过"时才去查 Redis。

### 代码示例

```python
import hashlib
import json
import math
import redis


class BloomFilter:
    def __init__(self, expected_items: int, false_positive_rate: float):
        self.size = math.ceil(
            -(expected_items * math.log(false_positive_rate)) / (math.log(2) ** 2)
        )
        self.hash_count = math.ceil((self.size / expected_items) * math.log(2))
        self.bit_array = bytearray(self.size)

    def _hashes(self, item: str):
        h1 = int(hashlib.md5(item.encode("utf-8")).hexdigest(), 16)
        h2 = int(hashlib.sha1(item.encode("utf-8")).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item: str):
        for pos in self._hashes(item):
            self.bit_array[pos] = 1

    def __contains__(self, item: str) -> bool:
        return all(self.bit_array[pos] == 1 for pos in self._hashes(item))


class EmbeddingCache:
    def __init__(self, expected_items=1000, false_positive_rate=0.05):
        self.bloom = BloomFilter(expected_items, false_positive_rate)
        self.redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    def _redis_key(self, text: str) -> str:
        return f"emb:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"

    def get_embedding(self, text: str):
        # 第一层：布隆过滤器
        if text not in self.bloom:
            print("布隆过滤器：一定没缓存过")
            embedding = model.encode(text)  # 调用真实模型
            self._write_to_cache(text, embedding)
            return embedding

        print("布隆过滤器：可能缓存过，去 Redis 确认")

        # 第二层：Redis
        key = self._redis_key(text)
        cached = self.redis_client.get(key)
        if cached is not None:
            print("Redis 命中 ✅")
            return json.loads(cached)

        # 布隆过滤器误判了
        print("Redis 未命中 ❌（误判）")
        embedding = model.encode(text)
        self._write_to_cache(text, embedding)
        return embedding

    def _write_to_cache(self, text: str, embedding: list):
        key = self._redis_key(text)
        self.redis_client.set(key, json.dumps(embedding))
        self.bloom.add(text)
```

完整可运行代码见：[demos/embedding_cache_demo.py](./demos/embedding_cache_demo.py)

### 运行方式

```bash
# 安装核心包
pip install -e .

# 基础 demo
python demos/basic_demo.py

# embedding 缓存 demo（需要 Docker + redis 可选依赖）
pip install -e ".[redis]"
python demos/embedding_cache_demo.py
```

这个 embedding demo 会：

1. 用 Docker 自动启动一个 Redis 容器。
2. 用 mock 的 embedding 模型模拟耗时计算。
3. 第一次查询某段文本时，走模型计算并写入 Redis。
4. 重复查询时，布隆过滤器判定"可能缓存过"，然后 Redis 命中，直接返回结果。

### 这种设计的 trade-off

- **优点**：大量减少 Redis 查询次数，降低缓存系统压力。
- **缺点**：有少量误判（布隆过滤器说可能缓存，但 Redis 没有），误判时只是多查一次 Redis，代价通常很小。

---

## 十、更多功能

这个仓库已经不只是一个 demo，核心代码在 `bloom_filter/` 包里，还包含了一些实用扩展。

### 批量添加

```python
bf.add_many(["url1", "url2", "url3"])
```

### 序列化到文件

```python
# 保存
with open("filter.bin", "wb") as f:
    f.write(bf.to_bytes())

# 加载
with open("filter.bin", "rb") as f:
    bf = BloomFilter.from_bytes(f.read())
```

也支持 JSON 友好的 dict 格式：`bf.to_dict()` / `BloomFilter.from_dict(...)`。

### 计数布隆过滤器（支持删除）

标准布隆过滤器不能删除。计数布隆过滤器把每个位换成计数器，支持 `remove()`：

```python
from bloom_filter import CountingBloomFilter

cbf = CountingBloomFilter(expected_items=1000, false_positive_rate=0.01)
cbf.add("hello")
assert "hello" in cbf

cbf.remove("hello")
assert "hello" not in cbf
```

> 注意：只有确认某个元素被添加过，才应该删除它。删除一个从未添加的元素可能误删其他元素共用的计数器，导致假阴性。

### 集合操作

两个配置相同的布隆过滤器可以做并集、交集：

```python
bf3 = bf1.union(bf2)
bf4 = bf1.intersection(bf2)
```

### 任意类型的 key

默认支持任意类型，会先用 `str()` 转成字符串再哈希：

```python
bf.add(42)
bf.add(("user", 10086))
```

也可以传入自定义 `key` 函数。

### 测试与基准

```bash
# 跑测试
pytest

# 跑性能基准（对比 Python set）
python benchmarks/benchmark.py
```

---

## 十一、总结

布隆过滤器就像一个**只会说两种话的门卫**：

- **"肯定没来过"** → 绝对可信。
- **"可能来过"** → 大概率可信，但最好再去查一下真正的名单确认。

它用极小的空间和极快的速度，帮我们快速过滤掉一大批"肯定不存在"的东西，是程序员手里非常实用的工具。
