# Reverse Engineering & Binary Exploitation

## Common CTF Binary Analysis
```bash
# Basic info
file binary
strings binary | grep -i flag
strings binary | grep -i ctf

# ELF analysis
readelf -h binary
readelf -s binary    # symbols
objdump -d binary    # disassembly

# Dynamic analysis
ltrace ./binary
strace ./binary
gdb ./binary
```

## Python Bytecode Reversing
```bash
# Decompile .pyc
pip install uncompyle6
uncompyle6 challenge.pyc > challenge.py

# Using pycdc (more modern)
pycdc challenge.pyc
```

## JavaScript Deobfuscation
- Use browser DevTools to beautify
- Use AST-based tools: `escodegen`, `babel`
- Replace `eval()` with `console.log()` to see decoded code
- Common obfuscation: JSFuck, jjencode, aaencode

## Common Crypto in CTF
```python
# Caesar cipher brute force
for shift in range(26):
    decoded = ''.join(chr((ord(c) - 65 + shift) % 26 + 65) if c.isupper()
                      else chr((ord(c) - 97 + shift) % 26 + 97) if c.islower()
                      else c for c in ciphertext)
    print(f"Shift {shift}: {decoded}")

# XOR brute force (single byte key)
for key in range(256):
    decoded = bytes([b ^ key for b in ciphertext])
    if b'flag' in decoded:
        print(f"Key {key}: {decoded}")

# Base64 variants
import base64
base64.b64decode(encoded)
base64.b32decode(encoded)
base64.b16decode(encoded)  # hex
```

## GDB Quick Reference
```
break main
run
next / step
print $rax
x/20x $rsp
info registers
disas main
```
