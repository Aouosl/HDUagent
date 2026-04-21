# 密码学分析 — 标准操作流程

## Phase 1: 识别密码学类型

```python
# 1. 检查文件/数据格式
# 常见编码识别
import base64, binascii

data = open("cipher.txt").read().strip()
print(f"长度: {len(data)}")
print(f"字符集: {set(data)}")

# 尝试常见解码
try: print("Base64:", base64.b64decode(data))
except: pass
try: print("Hex:", binascii.unhexlify(data))
except: pass
```

**快速判断：**
- 全是 hex 字符 (0-9a-f) → 十六进制编码
- 包含 `=` 结尾 + A-Za-z0-9+/ → Base64
- 包含 `-----BEGIN` → PEM 格式（RSA 公钥/私钥）
- 纯数字，非常大 → 可能是 RSA 的 n、e、c
- 看起来像乱码但可打印 → 可能是 XOR/Caesar/Vigenère

## Phase 2: 古典密码

### Caesar/ROT：
```python
# 暴力枚举所有偏移
for i in range(26):
    decoded = ''.join(chr((ord(c) - ord('a') + i) % 26 + ord('a')) if c.islower()
                      else chr((ord(c) - ord('A') + i) % 26 + ord('A')) if c.isupper()
                      else c for c in ciphertext)
    print(f"ROT{i}: {decoded}")
```

### Vigenère：
```python
# 使用 Kasiski 检测确定密钥长度，然后频率分析
# 或使用在线工具
```

### XOR：
```python
# 已知明文攻击
key = bytes(a ^ b for a, b in zip(ciphertext, known_plaintext))
print(f"Key: {key}")

# 单字节 XOR 暴力
for k in range(256):
    decoded = bytes(b ^ k for b in ciphertext)
    if all(32 <= c < 127 for c in decoded):
        print(f"Key 0x{k:02x}: {decoded}")
```

## Phase 3: 现代密码

### RSA：
```python
from Crypto.PublicKey import RSA
import gmpy2

# 如果给了公钥文件
key = RSA.import_key(open("public.pem").read())
n, e = key.n, key.e
print(f"n = {n}")
print(f"e = {e}")
print(f"n 的位数: {n.bit_length()}")

# 检查 n 是否可以分解
# factordb.com 或使用 yafu/msieve
# 如果 n 较小（< 256 bit），直接分解
# 如果 e 很小（e=3），考虑低指数攻击
# 如果有多组 (n, e, c) 共享因子，考虑公约数攻击

# 分解后解密
import gmpy2
p, q = ...  # 分解得到的因子
phi = (p - 1) * (q - 1)
d = gmpy2.invert(e, phi)
m = pow(c, d, n)
print(bytes.fromhex(hex(m)[2:]))
```

### AES：
```python
from Crypto.Cipher import AES

# ECB 模式（最简单，看密文是否有重复块）
cipher = AES.new(key, AES.MODE_ECB)
plaintext = cipher.decrypt(ciphertext)

# CBC 模式（需要 IV）
cipher = AES.new(key, AES.MODE_CBC, iv=iv)
plaintext = cipher.decrypt(ciphertext)

# Padding Oracle 攻击 — 如果服务端返回 padding 错误信息
```

## Phase 4: Hash 破解

```bash
# 识别 hash 类型
hashid "<hash_value>"
hash-identifier

# 使用 hashcat 或 john
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt    # MD5
hashcat -m 100 hash.txt /usr/share/wordlists/rockyou.txt  # SHA1
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
```

## Phase 5: 写结论

**结论必须包含：**
1. **密码类型**：使用了什么加密算法
2. **分析过程**：如何识别和破解
3. **密钥/明文**：解密结果
4. **Flag**（如果找到）

## 常见陷阱

| 陷阱 | 应对 |
|------|------|
| 多层编码 | Base64 → Hex → XOR，逐层剥离 |
| 自定义加密 | 先理解算法逻辑再破解，不要盲目暴力 |
| RSA n 太大 | 不要尝试直接分解，找其他攻击面（共享因子、低指数等）|
| 编码问题 | 注意 UTF-8 vs Latin-1，字节序等 |
